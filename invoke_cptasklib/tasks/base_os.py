from invoke import task

from invoke_cptasklib.tasks import libvirt
from invoke_cptasklib.tasks import packages
from invoke_cptasklib.tasks import util
from invoke_cptasklib.tasks.util import task_vars

#@task
#@task_vars
#def create_base(c, tvars, name="base"):
#	libvirt.create_vm(c, tvars, name)


ns = util.load_defaults()
#ns.add_task(libvirt.create_vm, name='create_vm', default=True)
#ns.add_task(libvirt.create_vm, name='create_base', default=True)
util.add_tasks(ns, module=libvirt, create_base='create_vm')
#util.add_tasks(ns, packages)

