import functools
from os import path
from io import StringIO

from invoke import task

from invoke_cptasklib.tasks import packages
from invoke_cptasklib.tasks import util
from invoke_cptasklib.tasks.util import task_vars
from invoke_cptasklib.tasks import file_util


@task
def ensure_disk_image(c, img_path, size_g=50, base=None):
    if file_util.is_file(c, img_path):
        return img_path
    file_dir, file_name = path.split(img_path)
    if not file_util.is_dir(c, file_dir):
        print("Creating image directory: {}".format(file_dir))
        file_util.dir(c, file_dir, sudo=True)
    print("Creating disk image at {}".format(img_path))
    file_prefix, file_ext = path.splitext(file_name)
    if len(file_ext) <= 1:
        raise Exception("Missing extension for disk image path: {}".format(
            file_name))
    file_ext = file_ext[1:]
    if base is not None:
        if file_ext not in ['qcow2']:
            raise Exception("Must have qcow2 if specifying a backing image")
    preallocation_arg = (
        "-o preallocation=metadata" if file_ext=="qcow2" and base is None
                                    else "")
    backing_file_arg = "" if base is None else "-b {}".format(base)
    c.run('sudo qemu-img create -f {fmt} {preallocation_arg} {backing} '
          '{path} {size}G'.format(path=img_path, fmt=file_ext,
                                  backing=backing_file_arg,
                                  preallocation_arg=preallocation_arg,
                                  size=size_g))
    return img_path

@task
def cat(c):
    c.run('cat', in_stream=StringIO("hi"))

@task
@task_vars
def meh(c, tvars, name='one'):
    print("Got {}".format(tvars.vm(instance_name=name)))
    print("Got {}".format(tvars.vm(vm="hi")))
    print("Got {}".format(tvars.vm(vm="{images_dir}")))
    print("Got {}".format(tvars.vm(instance_name=name, vm="{root_disk_arg}")))
    print("Got {}".format(tvars.vm_virt_install_cmd(instance_name=name)))
    print("Got {}".format(tvars.vm(vm="{root_disk_arg}")))

@task
@task_vars
def ensure_cloud_init_image(c, tvars, instance_name):
    image_path = tvars.cloud_init_floppy_path(instance_name=instance_name)
    c.run('sudo truncate --size 2M {}'.format(image_path))
    c.run('sudo mkfs.vfat -n cidata {}'.format(image_path))
    with c.cd(tvars.instance_disk_dir(instance_name=instance_name)):
        user_data = tvars.user_data(instance_name=instance_name)
        meta_data = tvars.meta_data(instance_name=instance_name)
        print("Creating user data")
        c.run('sudo tee user-data > /dev/null', in_stream=StringIO(user_data))
        print("Creating meta data")
        c.run('sudo tee meta-data > /dev/null', in_stream=StringIO(meta_data))
        c.run('sudo mcopy -oi {} user-data meta-data ::'.format(image_path))

@task
@task_vars
def ensure_distro_base_image(c, tvars):
    if path.exists(tvars.distro_disk_path()):
        return

    src = tvars.distro_download_path()

    # make sure we can process the download file (squashfs)
    file_results = c.run("file %s" % src, hide="stdout")
    if not file_results.ok or not 'Squashfs' in file_results.stdout:
        raise Exception("Need squashfs for input, got : {}".format(
            file_results.stdout))

    # create and format the image where the distro will be copied to
    distro_image = tvars.distro_raw_image_path()
    ensure_disk_image(c, distro_image)
    c.run("sudo mkfs.ext4 -L cloudimg-rootfs -F {}".format(distro_image))
    #c.run("sudo mkfs.ext3 -L cloudimg-rootfs -F {}".format(raw_file))

    distro_mount = tvars.distro_mount_dir()
    file_util.ensure_mount(c, distro_image, distro_mount)

    unpack_subdir = path.join(distro_mount, 'squashfs_unpack_dir')

    # unsquash into a subdirectory, move contents to right place
    print("unsquash distro")
    c.run('sudo unsquashfs -dest {} {}'.format(unpack_subdir, src))
    c.run('sudo mv {}/* {}'.format(unpack_subdir, distro_mount))
    c.run('sudo rmdir {}'.format(unpack_subdir))

    # unmount the distro raw image
    file_util.absent_mount(c, distro_mount)
    c.run('sudo rmdir {}'.format(distro_mount))

    # convert the raw image into qcow so it can be used as a base image
    c.run('sudo qemu-img convert -f raw -O qcow2 {} {}'.format(
        distro_image, tvars.distro_disk_pathi()))
    c.run('sudo rm {}'.format(distro_image))


def deprecated_ensure_vm_fs(c, name, fs_dir=None):
    file_util.dir(c, c.libvirt.squash_fs_images_dir, owner="root",
                  owner_group="libvirt", user="rx", group="rx", other="",
                  sudo=True)

    fs_dir = _get_vm_fs_parent_dir(c, name, fs_dir)
    file_util.dir(c, fs_dir, other="7")

    file_util.dir(c, path.join(fs_dir, name), other="")
    # the lower dir (read only filesystem) cannot be changed from root/755
    file_util.dir(c, path.join(fs_dir, name, 'lower'))
    for d in ["upper", "work", "merged"]:
        file_util.dir(c, path.join(fs_dir, name, d), other="")

    dirs = {d: path.join(fs_dir, name, d)
            for d in ["lower", "upper", "work", "merged"]}

    c.run("sudo mount -t squashfs -o loop {file} {mount}".format(
        file=path.join(c.libvirt.squash_fs_images_dir,
                       c.libvirt.squash_fs_base_filename),
        mount=dirs['lower']))

    c.run("sudo mount -t overlay "
          "-o lowerdir={lower},upperdir={upper},workdir={work}/ "
          "overlay {merged}".format(**dirs))

    return dirs['merged']


@task
@task_vars
def create_vm(c, tvars, name, single_user=False):
    overrides = dict(instance_name=name)

    ensure_distro_base_image(c)

    root_disk = tvars.root_disk(**overrides)
    ensure_disk_image(c, root_disk, base=tvars.distro_disk_path())

    ensure_cloud_init_image(c, instance_name=name)

    if single_user:
        overrides['kernel_args'] += ' ' + tvars.kernel_single_user_args()
        overrides['graphics_arg'] = tvars.no_graphics_arg()

    cmd = tvars.vm_virt_install_cmd(**overrides)

    print("Creating VM")
    c.run(cmd, pty=single_user, fallback=False)


ns = util.load_defaults()
util.add_tasks(ns, packages)
util.add_tasks(ns, file_util)
