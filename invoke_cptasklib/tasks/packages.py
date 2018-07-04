from invoke import task

from invoke_cptasklib.tasks import util


def installed(c):
    a = c.run("dpkg-query -f '${binary:Package}\n' -W", hide=True)
    # some output is like zlib1g:amd64
    return [p.split(":")[0] for p in a.stdout.splitlines()]


@task(default=True)
def print_installed(c):
    for p in installed(c):
        print(p)


@task(iterable=['pkgs'])
def install(c, pkgs):
    cmd_fmt = "sudo apt install -y {}"
    if not pkgs:
        pkgs = c.packages.install
    if pkgs is None:
        return
    print("Installing packages")
    util.add_missing(c, cmd_fmt, "package", installed, pkgs)


@task(iterable=['pkgs'])
def uninstall(c, pkgs):
    cmd_fmt = "sudo apt remove -y {}"
    if not pkgs:
        pkgs = c.packages.uninstall
    if pkgs is None:
        return
    print("Uninstalling packages")
    util.remove_present(c, cmd_fmt, "package", installed, pkgs)


ns = util.load_defaults()
