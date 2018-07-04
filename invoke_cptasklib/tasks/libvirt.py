from os import path
from os import environ

from invoke import task
from invoke.exceptions import Exit
from functools import partial

from invoke_cptasklib.tasks import packages
from invoke_cptasklib.tasks import util
from invoke_cptasklib.tasks import file_util


def get_disk_path(c, instance_name, disk_name, img_format="qcow2"):
    img_name = 'disk-' + disk_name + '.' + img_format
    return path.join(c.libvirt.qcow_images_parent_dir, instance_name, img_name)


@task
def ensure_instance_disk_image(c, instance_name, disk_name, size_g=50, img_format='qcow2'):
    img_path = get_disk_path(instance_name, disk_name, img_format)
    ensure_disk_image(c, img_path, size_g, img_format)

@task
def ensure_disk_image(c, img_path, size_g=50, img_format=None, base=None):
    if file_util.is_file(c, img_path):
        return img_path
    file_util.dir(c, path.join(*path.split(img_path)[:-1]), sudo=True)

    print("Creating disk image at {}".format(img_path))
    if base is not None:
        if img_format not in [None, 'qcow2']:
            raise Exception("Must have qcow2 if specifying a backing image")
        img_format = 'qcow2'
    if img_format is None:
        img_format = 'raw'
    preallocation_arg = ("" if img_format=="raw" or base is not None
                         else "-o preallocation=metadata")
    img_format = "raw" if img_format is None else img_format
    backing_file_arg = "" if base is None else "-b {}".format(base)
    c.run('sudo qemu-img create -f {fmt} {preallocation_arg} {backing} '
          '{path} {size}G'.format(path=img_path, fmt=img_format,
                                  backing=backing_file_arg,
                                  preallocation_arg=preallocation_arg,
                                  size=size_g))
    return img_path


@task
def deprecated_absent_vm_fs(c, name, fs_dir=None):
    if fs_dir is None:
        fs_dir = path.join(environ["HOME"], ".kvm-mounts")

    dirs = {d: path.join(fs_dir, name, d)
            for d in ["lower", "upper", "work", "merged"]}

    c.run("sudo umount {merged}".format(merged=dirs['merged']))
    c.run("sudo umount {lower}".format(lower=dirs['lower']))

    file_util.absent_dir(c, path.join(
        fs_dir, name, 'work/work'), recursive=True)
    for d in ["lower", "upper", "work", "merged", ""]:
        file_util.absent_dir(c, path.join(fs_dir, name, d))


def _get_vm_fs_parent_dir(c, name, fs_dir):
    if fs_dir is not None:
        return fs_dir
    #return path.join(environ["HOME"], ".kvm-mounts")
    return path.join('/srv', "kvm-mounts", name)


@task
def ensure_root_image(c, instance_name, base_image_name=None):
    target_dir = path.join(c.libvirt.qcow_images_parent_dir, instance_name)
    target = path.join(target_dir, 'disk_root.qcow2')
    if file_util.exists(c, target):
        return

    # default the base image filename if not supplied
    if base_image_name is None:
        base_image_name, _ = path.splitext(c.libvirt.default_distro_filename)

    # add .img if user supplied just the name
    [base_name, base_extension] = path.splitext(base_image_name)
    if base_extension != '.qcow2':
        base_image_name = base_image_name + '.qcow2'

    # put it in the base images directory
    base_image_path = path.join(c.libvirt.qcow_images_parent_dir,
                                'distro_bases', base_image_name)

    if not file_util.exists(c, base_image_path):
        raise Exception("Distribution source image not available: {}".format(
            base_image_path))

    # create the image using the distro image as backing file
    file_util.dir(c, target_dir, sudo=True)
    ensure_disk_image(c, target, base=base_image_path)


# TODO: fix the root image so it's shared
@task
def ensure_distro_base_image(c, distro_filename=None):
    target_dir = path.join(c.libvirt.qcow_images_parent_dir, 'distro_bases')
    if distro_filename is None:
        distro_filename = c.libvirt.default_distro_filename
    [src_name, src_extension] = path.splitext(distro_filename)
    if src_extension and src_extension in [".squashfs", ".sfs"]:
        target_file = path.join(target_dir, src_name + '.qcow2')
        raw_file = path.join(target_dir, src_name + '.img')
        target_mount = path.join(target_dir, src_name + "_root_mnt")
    else:
        target_file = path.join(target_dir, distro_filename + '.qcow2')
        raw_file = path.join(target_dir, distro_filename + '.img')
        target_mount = path.join(target_dir, distro_filename + "_root_mnt")
    if path.exists(target_file):
        return
    src = path.join(c.libvirt.distro_downloads_dir, distro_filename)
    if not file_util.exists(c, src):
        raise Exception("Distribution source image not available: {}".format(
            src))
    file_results = c.run("file %s" % src, hide="stdout")
    if not file_results.ok or not 'Squashfs' in file_results.stdout:
        raise Exception("Need squashfs for input, got : {}".format(
            file_results.stdout))

    ensure_disk_image(c, raw_file)
    #c.run("sudo mkfs.ext4 -F {}".format(raw_file))
    c.run("sudo mkfs.ext3 -L cloudimg-rootfs -F {}".format(raw_file))
    print("ensuring mount")
    file_util.ensure_mount(c, raw_file, target_mount)
    print("unpack squashed image subdirectory")
    target_subdir = path.join(target_mount, 'squashfs_unpack_dir')
    c.run('sudo unsquashfs -dest {} {}'.format(target_subdir, src))
    c.run('sudo mv {}/* {}'.format(target_subdir, target_mount))
    c.run('sudo rmdir {}'.format(target_subdir))
    file_util.absent_mount(c, target_mount)
    c.run('sudo rmdir {}'.format(target_mount))
    c.run('sudo qemu-img convert -f raw -O qcow2 {} {}'.format(
        raw_file, target_file))
    c.run('sudo rm {}'.format(raw_file))


@task
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


@task()
def create_fs_vm(c, name, fs_dir=None):
    #ensure_vm_fs(c, name)
    fs_dir = _get_vm_fs_parent_dir(c, name, fs_dir)
    cmd = c.libvirt.fs_vm_virt_install_tmpl.format(
        name=name, root=fs_dir+'/merged', **c.libvirt)
    c.run(cmd)


@task
def create_vm(c, name, recovery=False):
    #cdrom_tmpl = "" if not cdrom else "--cdrom={}".format(cdrom)
    #location_tmpl = "" if not location else "--location={}".format(location)
    #pxe_tmpl = "" if not pxe else "--pxe"

    vm_dict = dict(c.libvirt.vm_defaults)
    # TODO: update from CLI arguments

    root_disk = path.join(c.libvirt.qcow_images_parent_dir,
                     name,
                     'disk_root.qcow2')
    disks = c.libvirt.cloud_init_disks_tmpl.format(
        disk=root_disk, floppy_path=vm_dict['cloud_init_floppy_path'])

    kernel_args = 'root=/dev/vda'
    if recovery:
        kernel_args = kernel_args + ' ' + c.libvirt.kernel_recovery_mode_args

    vm_dict.update(dict(
        name=name,
        disks=disks,
        kernel_args=kernel_args,
    ))

    cmd = c.libvirt.vm_virt_install_tmpl.format(**vm_dict)
    if recovery:
        cmd = cmd + " --graphics none"
    c.run(cmd, pty=recovery, fallback=False)

ns = util.load_defaults()
util.add_tasks(ns, packages)
util.add_tasks(ns, file_util)
