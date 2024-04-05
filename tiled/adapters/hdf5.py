import collections.abc
import os
import warnings

import h5py
import numpy

from ..adapters.utils import IndexersMixin
from ..iterviews import ItemsView, KeysView, ValuesView
from ..structures.core import StructureFamily
from ..utils import node_repr, path_from_uri
from .array import ArrayAdapter
from .resource_cache import with_resource_cache

SWMR_DEFAULT = bool(int(os.getenv("TILED_HDF5_SWMR_DEFAULT", "0")))
INLINED_DEPTH = int(os.getenv("TILED_HDF5_INLINED_CONTENTS_MAX_DEPTH", "7"))


def hdf5_lookup(
    data_uri,
    *,
    structure=None,
    metadata=None,
    swmr=SWMR_DEFAULT,
    libver="latest",
    specs=None,
    access_policy=None,
    path=None,
):
    path = path or []
    adapter = HDF5Adapter.from_uri(
        data_uri,
        structure=structure,
        metadata=metadata,
        swmr=swmr,
        libver=libver,
        specs=specs,
        access_policy=access_policy,
    )
    for segment in path:
        adapter = adapter.get(segment)
        if adapter is None:
            raise KeyError(segment)
    # TODO What to do with metadata, specs?
    return adapter


def from_dataset(dataset):
    return ArrayAdapter.from_array(dataset, metadata=getattr(dataset, "attrs", {}))


class HDF5Adapter(collections.abc.Mapping, IndexersMixin):
    """
    Read an HDF5 file or a group within one.

    This map the structure of an HDF5 file onto a "Tree" of array structures.

    Examples
    --------

    From the root node of a file given a filepath

    >>> import h5py
    >>> HDF5Adapter.from_uri("file://localhost/path/to/file.h5")

    From the root node of a file given an h5py.File object

    >>> import h5py
    >>> file = h5py.File("path/to/file.h5")
    >>> HDF5Adapter.from_file(file)

    From a group within a file

    >>> import h5py
    >>> file = h5py.File("path/to/file.h5")
    >>> HDF5Adapter(file["some_group']["some_sub_group"])

    """

    structure_family = StructureFamily.container

    def __init__(
        self, node, *, structure=None, metadata=None, specs=None, access_policy=None
    ):
        self._node = node
        self._access_policy = access_policy
        self.specs = specs or []
        self._provided_metadata = metadata or {}
        super().__init__()

    @classmethod
    def from_file(
        cls,
        file,
        *,
        structure=None,
        metadata=None,
        swmr=SWMR_DEFAULT,
        libver="latest",
        specs=None,
        access_policy=None,
    ):
        return cls(file, metadata=metadata, specs=specs, access_policy=access_policy)

    @classmethod
    def from_uri(
        cls,
        data_uri,
        *,
        structure=None,
        metadata=None,
        swmr=SWMR_DEFAULT,
        libver="latest",
        specs=None,
        access_policy=None,
    ):
        filepath = path_from_uri(data_uri)
        cache_key = (h5py.File, filepath, "r", swmr, libver)
        file = with_resource_cache(
            cache_key, h5py.File, filepath, "r", swmr=swmr, libver=libver
        )
        return cls.from_file(file)

    def __repr__(self):
        return node_repr(self, list(self))

    @property
    def access_policy(self):
        return self._access_policy

    def structure(self):
        return None

    def metadata(self):
        d = dict(self._node.attrs)
        for k, v in list(d.items()):
            # Convert any bytes to str.
            if isinstance(v, bytes):
                d[k] = v.decode()
        d.update(self._provided_metadata)
        return d

    def __iter__(self):
        yield from self._node

    def __getitem__(self, key):
        value = self._node[key]
        if isinstance(value, h5py.Group):
            return HDF5Adapter(value)
        else:
            if value.dtype == numpy.dtype("O"):
                warnings.warn(
                    f"The dataset {key} is of object type, using a "
                    "Python-only feature of h5py that is not supported by "
                    "HDF5 in general. Read more about that feature at "
                    "https://docs.h5py.org/en/stable/special.html. "
                    "Consider using a fixed-length field instead. "
                    "Tiled will serve an empty placeholder, unless the "
                    "object is of size 1, where it will attempt to repackage "
                    "the data into a numpy array."
                )

                check_str_dtype = h5py.check_string_dtype(value.dtype)
                if check_str_dtype.length is None:
                    dataset_names = value.file[self._node.name + "/" + key][...][()]
                    if value.size == 1:
                        arr = numpy.array(dataset_names)
                        return from_dataset(arr)
                return from_dataset(numpy.array([]))
            return from_dataset(value)

    def __len__(self):
        return len(self._node)

    def keys(self):
        return KeysView(lambda: len(self), self._keys_slice)

    def values(self):
        return ValuesView(lambda: len(self), self._items_slice)

    def items(self):
        return ItemsView(lambda: len(self), self._items_slice)

    def search(self, query):
        """
        Return a Tree with a subset of the mapping.
        """
        raise NotImplementedError

    def read(self, fields=None):
        if fields is not None:
            raise NotImplementedError
        return self

    # The following two methods are used by keys(), values(), items().

    def _keys_slice(self, start, stop, direction):
        keys = list(self._node)
        if direction < 0:
            keys = reversed(keys)
        return keys[start:stop]

    def _items_slice(self, start, stop, direction):
        items = [(key, self[key]) for key in list(self)]
        if direction < 0:
            items = reversed(items)
        return items[start:stop]

    def inlined_contents_enabled(self, depth):
        return depth <= INLINED_DEPTH
