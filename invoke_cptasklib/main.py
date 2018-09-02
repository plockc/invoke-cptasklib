from invoke import Collection
from invoke import Program

import invoke_cptasklib.tasks.libvirt as libvirt
import invoke_cptasklib.tasks.base_os as base_os
#import invoke_cptasklib.tasks.base_os as base_os

namespace = Collection()
namespace.add_collection(libvirt.ns, name='libvirt')
namespace.add_collection(base_os.ns, name='base_os')
#program = Program(namespace=namespace, version='0.1')
program = Program(namespace=namespace)
#program = Program(namespace=Collection.from_module(libvirt), version='0.1')
