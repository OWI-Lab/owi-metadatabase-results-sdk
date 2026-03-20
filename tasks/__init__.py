from invoke import Collection

from . import docs, quality, test

ns = Collection()
ns.add_collection(Collection.from_module(test))
ns.add_collection(Collection.from_module(quality), name="qa")
ns.add_collection(Collection.from_module(docs))
