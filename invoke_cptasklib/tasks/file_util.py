import os

from invoke import task
from invoke.exceptions import Exit

@task
# TODO: convert to *paths
def dir(c, path, owner=None, owner_group=None, user=None,
        group=None, other=None, sudo=False):
    sudo_cmd = "sudo " if sudo is True else ""
    if not is_dir(c, path):
        c.run(sudo_cmd + "mkdir " + path)
    set_owner(c, path, owner, owner_group, sudo)
    ensure_mode(c, path, user=user, group=group, other=other, sudo=sudo)


@task
def absent_dir(c, path, recursive=False):
    if not exists(c, path):
        return
    if recursive is True:
        c.run("sudo rm -rf {}".format(path))
        return
    c.run("sudo rmdir {}".format(path))


@task
def set_owner(c, path, owner=None, group=None, sudo=False):
    sudo_cmd = "sudo " if sudo is True else ""
    cmd = "chown"
    if owner is None and group is None:
        return
    grp_cmd = "" if group is None else ":" + group
    owner_cmd = "" if group is None else owner
    if not owner_cmd and not grp_cmd:
        return
    c.run(sudo_cmd + cmd + " " + owner_cmd + grp_cmd + " " + path)


@task
def ensure_mode(c, path, mode=None, user=None, group=None, other=None, sudo=False):
    if not file_util.exists(c, path):
        raise Exception("Cannot set mode for path that does not exist: {}".format(
            path))

    params = dict(u=user, g=group, o=other, a=mode)

    mode_map = {"0": "", "1": "x", "2": "w", "3": "wx", "4": "r",
                "5": "rx", "6": "rw", "7": "rwx"}

    # if mapping from numeric to letters exist, map else keep it as is
    params = {k: mode_map.get(str(v), v) for k, v in params.items()
              if v is not None}

    if mode is not None and set([user, group, other]) != set([None]):
        Exit("when using mode, cannot set user/group/other")

    u, g, o = tuple(c.run('stat --format "%a" {}'.format(path)).stdout.strip())
    cur_mode = dict(u=mode_map[u], g=mode_map[g], o=mode_map[o])

    if any(v for v in params.values() if not set(v).issubset("rwx")):
            raise Exception(
                "use letters from rwx not '{}' for setting mode".format(
                    "|".join(
                        set(l for v in params.values() for l in v) - set("rwx")
                )))

    sudo_cmd = "sudo " if sudo is True else ""
    cmd = "chmod "

    # get mode assignments for ugo, only if there is a difference
    modes = [scope + "=" + v for scope, v in params.items()
             if v is not None and v != cur_mode[scope]]
    # if there are no changes, do nothing
    if not modes:
        return

    c.run(sudo_cmd + cmd + ",".join(modes) + " " + path)


def is_file(c, *paths):
    full_path = os.path.join(paths[0], *paths[1:])
    return c.run("test -f {}".format(full_path), warn=True).ok


def is_dir(c, *paths):
    full_path = os.path.join(paths[0], *paths[1:])
    return c.run("test -d {}".format(full_path), warn=True).ok


def exists(c, *paths):
    full_path = os.path.join(paths[0], *paths[1:])
    return c.run("test -e {}".format(full_path), warn=True).ok
