import functools

from invoke import task

from invoke_cptasklib.tasks import util


def groups(c, uid):
    return c.run("groups").split(" ")


@ task
def print_groups(c, uid):
    for g in groups(c, uid):
        print("{} is in group {}".format(uid, g))

@task(iterable=['groups'])
def user(c, uid, extra_groups, append_groups=True):
    if extra_groups:
        if append_groups:
            cmd_format = "usermod --append --groups {}"
        else:
            cmd_format = "usermod --groups {}"
        util.add_missing(
            cmd_format, "group", functools.partial(groups(uid)), extra_groups)
