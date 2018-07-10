import functools
import inspect
from itertools import dropwhile
import os
import re
import time
import yaml

from invoke import Collection
from invoke.tasks import Task

def get_present_and_missing(now, desired, delimiters=", ;"):
    """Determine items already present and missing
    :param now: delimited words for what is present
    :param desired: delimited words for what is desired
    :returns: sorted list of words (present, missing)
    """
    now = set(n for e in now for n in re.split("[{}]".format(delimiters), e))
    desired = set(d for e in desired for d in re.split("[{}]".format(delimiters), e))

    present = list(sorted(desired.intersection(now)))
    missing = list(sorted(desired - now))

    return (present, missing)


def add_missing(c, cmd_fmt, noun, items_func, ensure_items,
                render_func=lambda items: " ".join(items)):
    """
    :param cmd_fmt: {} format string with single value replacement
        for all missing items
    :param render_func: f(list of missing) -> value for cmd_fmt
    """
    present, missing = get_present_and_missing(items_func(c), ensure_items)
    if missing:
        for e in missing:
            print("adding {}: {}".format(noun, e))
        rendered_missing = render_func(missing)
        c.run(cmd_fmt.format(rendered_missing))
    if present:
        for e in present:
            print("{} already present: {}".format(noun, e))
    _, missing = get_present_and_missing(items_func(c), ensure_items)
    if missing:
        for m in missing:
            print("Failed to add {}: {}".format(noun, m))
        raise Exception("Failed to add some {}: {}".format(
            noun, render_func(missing)))


def remove_present(c, cmd_fmt, noun, items_func, remove_items,
                render_func=lambda items: " ".join(items)):
    """
    :param cmd_fmt: {} format string with single value replacement
        for all items
    :param render_func: f(list of missing) -> value for cmd_fmt
    """
    present, missing = get_present_and_missing(items_func(c), remove_items)
    if present:
        for e in present:
            print("removing {}: {}".format(noun, e))
        rendered_to_remove = render_func(present)
        c.run(cmd_fmt.format(rendered_to_remove))
    if missing:
        for e in missing:
            print("{} already absent: {}".format(noun, e))
    present, _ = get_present_and_missing(items_func(c), remove_items)
    if present:
        for p in present:
            print("Failed to remove {}: {}".format(noun, p))
        raise Exception("Failed to remove some {}: {}".format(
            noun, render_func(present)))

def task_vars(task):
    # this will be to tell variable_lookup which vars to look at
    module_name = task.__module__.split('.')[-1]
    # create the function to expose to Task that does all the magic
    # including calling the final function with an extra task_vars
    # parameters that can handle attribute or dict lookups, and
    # those can be called as a function if key value pairs need
    # to be set for name value pairs
    def call_task(c, *args, **kwargs):
        class task_vars:
            # handle dict lookups
            def __getitem__(self, i):
                #TODO: replace with value, and set __call__ for kwarg
                return functools.partial(variable_lookup, c, i,
                                         module_name)
            # handle attribute lookups
            def __getattribute__(self, i):
                #TODO: replace with value, and set __call__ for kwarg
                return functools.partial(variable_lookup, c, i,
                                         module_name)
        task(c, *args, task_vars=task_vars(), **kwargs)
    # fake out invoke Task with name, module, and signature
    call_task.__name__  = task.__name__
    call_task.__module__  = task.__module__
    # inspect.signature creates a Signature object
    # Signature.parameters is a dict of name to Parameter objects
    # filter out the 'task_vars' parameter that we injected and
    # create a new Signature with that to expose to Task
    # the __signature__ attribute tells inspect what to report the params are
    call_task.__signature__ = inspect.signature(task).replace(
        parameters=[p[1] for p in inspect.signature(task).parameters.items()
                    if p[0] != 'task_vars'])
    return call_task

# brute force lookups, could build dependency graphs to speed lookups
def variable_lookup(c, name, module_short_name, **kwargs):
    vars_dict = dict(c.config[module_short_name])

    # if any kwarg overrides a value in a template dict, then
    # that dict plus all the remaining have to be re-evaluated
    # for this lookup
    dicts_to_eval = list(
        dropwhile(lambda d: not (set(d) & set(kwargs)),
                  c.config.get('cptasks_module_defaults', [])))

    for dict_to_eval in dicts_to_eval:
        # when a key appears in dict_to_eval that is in kwargs,
        # we include the kwarg override and defer the over kwargs
        # until later as they may rely on vars that have not been
        # defined yet
        overrides = set(kwargs) & set(dict_to_eval)

        # use the kwargs rendered values instead of dict_to_eval's
        # dict_to_eval needs to be a copy so make a new one
        dict_to_eval = {k: v for k, v in dict_to_eval.items()
                        if k not in overrides}
        for k in overrides:
            vars_dict[k] = format_strings(vars_dict, kwargs[k])

        vars_dict.update(format_strings(vars_dict, dict_to_eval))
    # re-apply here in case the requested var was overriden in kwargs
    vars_dict.update(kwargs)
    return format_strings(vars_dict, vars_dict[name])

def format_strings(var_dict, to_format):
    if isinstance(to_format, str):
        return to_format.format(**var_dict)
    if isinstance(to_format, dict):
        return {k: format_strings(var_dict, v)
                   for k, v in to_format.items()}
    if isinstance(to_format, list):
        return [format_strings(var_dict, elem) for elem in to_format]
    return to_format

def load_defaults(collection=None):
    """Update collection configuration with defaults from a .yml file

    The .yml file is in the same directory as the calling module,
    and the .py extension is replaced with .yml
    :param collection: the collection to update or if None,
        a new Collection will be created with all the tasks in the module
    :returns: the updated Collection
    """
    caller_frame_record = inspect.stack()[1]
    caller_path = caller_frame_record[1]
    caller_frame = caller_frame_record[0]

    calling_module = inspect.getmodule(caller_frame)
    if collection is None:
        collection = Collection()
        module_tasks = [
            t for _, t in inspect.getmembers(calling_module)
            if isinstance(t, Task)]
        for t in module_tasks:
            collection.add_task(t)

    if not caller_path.endswith(".py"):
        return collection
    default_path = caller_path[:-3] + ".yml"
    if os.path.isfile(default_path):
        with open(default_path) as f:
            print("loaded defaults from {}".format(default_path))
            # TODO: load up all them dicts
            module_vars = {}
            cptasks_module_defaults = list(yaml.safe_load_all(f))
            for var_dict in cptasks_module_defaults:
                formatted_vars = format_strings(module_vars, var_dict)
                module_vars.update(formatted_vars)
            module_short_name = calling_module.__name__.split('.')[-1]
            collection.configure({
                module_short_name: module_vars,
                'cptasks_module_defaults': cptasks_module_defaults})
    return collection


# TODO: split up the load defaults above so can load the passed in module's
#  defaults before overriding
def add_tasks(ns, module, *tasks):
    calling_module = inspect.getmodule(inspect.stack()[1][0])
    calling_module_short_name = calling_module.__name__.split('.')[-1]

    module_name = module.__name__.split('.')[-1]

    # create new collection and add the requested task
    # this allows us to create a configuration specific to this collection
    if tasks:
        for task in tasks:
            collection = Collection(module_name)
            task = getattr(module, task)
            collection.add_task(task)
    else:
        collection = Collection.from_module(module)

    ns.add_collection(collection)

    if not calling_module_short_name in ns.configuration():
        return
    calling_module_configuration = ns.configuration()[calling_module_short_name]
    if not module_name in calling_module_configuration:
        return
    module_configuration = calling_module_configuration[module_name]
    collection.configure({module_name: module_configuration})


def wait_for_true(func, max_seconds=30, recheck_delay=10,
                  raise_ex=True, *args, **kwargs):
    def check():
        try:
            return func(*args, **kwargs)
        except BaseException as e:
            return e

    if check() is True:
        return True

    timeout_time = time.time() + max_seconds
    while time.time() < timeout_time:
        time.sleep(recheck_delay)
        status = check()
        if status is True:
            return True

    if raise_ex:
        raise Exception("Timeout waiting for condition: {}".format(status))

    return status
