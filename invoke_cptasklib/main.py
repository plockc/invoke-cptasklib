from invoke import Collection
from invoke import Program
import invoke_cptasklib.tasks.libvirt as libvirt

#program = Program(namespace=Collection.from_module(libvirt), version='0.1')
program = Program(namespace=libvirt.ns, version='0.1')
