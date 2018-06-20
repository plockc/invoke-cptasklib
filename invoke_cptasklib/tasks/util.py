import inspect
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

    if collection is None:
        collection = Collection()
        calling_module = inspect.getmodule(caller_frame)
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
            defaults = yaml.safe_load(f)
        collection.configure(defaults)

    return collection


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
