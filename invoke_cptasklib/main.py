from invoke import Collection
from invoke import Program
import invoke_cptasklib
import invoke_cptasklib.tasks.file_util as file_util

program = Program(namespace=Collection.from_module(file_util), version='0.1')

