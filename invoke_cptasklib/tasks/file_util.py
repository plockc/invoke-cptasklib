from os.path import ismount

from invoke import task
from invoke.exceptions import Exit

@task
# TODO: convert to *paths
def dir(c, path, owner=None, owner_group=None, user=None,
        group=None, other=None, sudo=False):
    sudo_cmd = "sudo " if sudo is True else ""
    if not is_dir(c, path):
        c.run(sudo_cmd + "mkdir -p " + path)
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
    if not exists(c, path):
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


def is_file(c, path):
    return c.run("test -f {}".format(path), warn=True).ok


def is_dir(c, path):
    return c.run("test -d {}".format(path), warn=True).ok


def exists(c, path):
    return c.run("test -e {}".format(path), warn=True).ok

@task
def absent_mount(c, target_dir):
    if not exists(c, target_dir):
        return
    if is_file(c, target_dir):
        raise Exception("Expected directory instead of file: {}".format(
            target_dir))
    if ismount(target_dir):
        print("Unmounting {}".format(target_dir))
        c.run("sudo umount {}".format(target_dir))
        return

@task
def ensure_mount(c, device, target_dir, dev_type=None):
    if ismount(target_dir):
        mounts = c.run("cat /proc/self/mounts").stdout.splitlines()
        mount_info = next((line for line in mounts if line.split()[1] == target_dir), None)
        if mount_info is None:
            raise Exception("Odd, {} is a mount but not found in /proc/self/mounts".format(target_dir))
        if mount_info.split()[0] != device:
            raise Exception("Wrong device ({}) mounted at {}".format(
                device, target_dir))
        return
    dir(c, target_dir, sudo=True)
    type_arg = "" if dev_type is None else "-t {}".format(dev_type)
    print("Mounting {} at {}".format(device, target_dir))
    c.run("sudo mount " + type_arg + "{} {}".format(device, target_dir))
