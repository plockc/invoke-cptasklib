# This is mounting filesystems to guest instead of device images (like qcow with backing images)
Mount the squashfs image from ubuntu
  mount -t squashfs \
      /var/lib/libvirt/squashfs-images/bionic-server-cloudimg-amd64.squashfs \
      /var/lib/libvirt/squashfs-mounts/bionic-server-cloudimg-amd64

Mount squashfs with overlayfs so that user dir is the VM root filesystem
  loaderdir=/squashfs
  upperdir=$HOME/.kvm-mounts/test/upper
  workdir=$HOME/.kvm-mounts/test/work

mount the merged directory though 9p, using fsdev


