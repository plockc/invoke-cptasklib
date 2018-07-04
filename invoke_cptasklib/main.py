from invoke import Collection
from invoke import Program
import invoke_cptasklib.tasks.file_util as file_util
import invoke_cptasklib.tasks.libvirt as libvirt

program = Program(namespace=Collection.from_module(libvirt), version='0.1')

