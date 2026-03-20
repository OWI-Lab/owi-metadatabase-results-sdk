from invoke import Collection

from . import docs, quality, test

ns = Collection()
ns.add_collection(test)
ns.add_collection(quality, name="qa")
ns.add_collection(docs)
