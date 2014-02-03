#!/usr/bin/env python3

import sys
import os
import os.path
import posixpath
import string
import math
import random
import collections

import numpy as np
import numpy.testing as npt
import numpy.random

import hdf5storage


random.seed()


class TestPythonMatlabFormat(object):
    # Test for the ability to write python types to an HDF5 file that
    # type information and matlab information are stored in, and then
    # read it back and have it be the same.
    def __init__(self):
        self.filename = 'data.mat'
        self.options = hdf5storage.Options()

        # Need a list of the supported numeric dtypes to test.
        self.dtypes = ['bool', 'uint8', 'uint16', 'uint32', 'uint64',
                       'int8', 'int16', 'int32', 'int64', 'float16',
                       'float32', 'float64', 'complex64', 'complex128',
                       'bytes', 'str']

        # Define the sizes of random datasets to use.
        self.max_string_length = 10
        self.max_array_axis_length = 8
        self.max_list_length = 6
        self.max_posix_path_depth = 5
        self.max_posix_path_lengths = 17
        self.object_subarray_dimensions = 2
        self.max_object_subarray_axis_length = 5

    def random_str_ascii(self, length):
        # Makes a random ASCII str of the specified length.
        ltrs = string.ascii_letters + string.digits
        return ''.join([random.choice(ltrs) for i in range(0, length)])

    def random_bytes(self, length):
        # Makes a random sequence of bytes of the specified length from
        # the ASCII set.
        ltrs = bytes(range(1, 127))
        return bytes([random.choice(ltrs) for i in range(0, length)])

    def random_int(self):
        return random.randint(-(2**63 - 1), 2**63)

    def random_float(self):
        return random.uniform(-1.0, 1.0) \
            * 10.0**random.randint(-300, 300)

    def random_numpy(self, shape, dtype):
        # Makes a random numpy array of the specified shape and dtype
        # string. The method is slightly different depending on the
        # type. For 'bytes', 'str', and 'object'; an array of the
        # specified size is made and then each element is set to either
        # a numpy.bytes_, numpy.str_, or some other object of any type
        # (here, it is a randomly typed random numpy array). If it is
        # any other type, then it is just a matter of constructing the
        # right sized ndarray from a random sequence of bytes (all must
        # be forced to 0 and 1 for bool).
        if dtype in 'bytes':
            length = random.randint(1, self.max_string_length)
            data = np.zeros(shape=shape, dtype='S' + str(length))
            for x in np.nditer(data, op_flags=['readwrite']):
                x[...] = np.bytes_(self.random_bytes(length))
            return data
        elif dtype == 'str':
            length = random.randint(1, self.max_string_length)
            data = np.zeros(shape=shape, dtype='U' + str(length))
            for x in np.nditer(data, op_flags=['readwrite']):
                x[...] = np.str_(self.random_str_ascii(length))
            return data
        elif dtype == 'object':
            data = np.zeros(shape=shape, dtype='object')
            for index, x in np.ndenumerate(data):
                data[index] = self.random_numpy( \
                    shape=self.random_numpy_shape( \
                    self.object_subarray_dimensions, \
                    self.max_object_subarray_axis_length), \
                    dtype=random.choice(self.dtypes))
            return data
        else:
            nbytes = np.ndarray(shape=(1,), dtype=dtype).nbytes
            bts = np.random.bytes(nbytes * np.prod(shape))
            if dtype == 'bool':
                bts = b''.join([{True: b'\x01', False: b'\x00'}[ \
                    ch > 127] for ch in bts])
            return np.ndarray(shape=shape, dtype=dtype, buffer=bts)

    def random_numpy_scalar(self, dtype):
        # How a random scalar is made depends on th type. For must, it
        # is just a single number. But for the string types, it is a
        # string of any length.
        if dtype == 'bytes':
            return np.bytes_(self.random_bytes(random.randint(1,
                             self.max_string_length)))
        elif dtype == 'str':
            return np.str_(self.random_str_ascii(
                           random.randint(1, self.max_string_length)))
        else:
            return self.random_numpy(tuple(), dtype)[()]

    def random_numpy_shape(self, dimensions, max_length):
        # Makes a random shape tuple having the specified number of
        # dimensions. The maximum size along each axis is max_length.
        return tuple([random.randint(1, max_length) for x in range(0,
                     dimensions)])

    def random_list(self, N, python_or_numpy='numpy'):
        # Makes a random list of the specified type. If instructed, it
        # will be composed entirely from random numpy arrays (make a
        # random object array and then convert that to a
        # list). Otherwise, it will be a list of random bytes.
        if python_or_numpy == 'numpy':
            return self.random_numpy((N,), dtype='object').tolist()
        else:
            data = []
            for i in range(0, N):
                data.append(self.random_bytes(random.randint(1,
                            self.max_string_length)))
            return data

    def random_name(self):
        # Makes a random POSIX path of a random depth.
        depth = random.randint(1, self.max_posix_path_depth)
        path = '/'
        for i in range(0, depth):
            path = posixpath.join(path, self.random_str_ascii(
                                  random.randint(1,
                                  self.max_posix_path_lengths)))
        return path

    def write_readback(self, data, name, options):
        # Write the data to the proper file with the given name, read it
        # back, and return the result. The file needs to be deleted
        # before and after to keep junk from building up.
        if os.path.exists(self.filename):
            os.remove(self.filename)
        try:
            hdf5storage.write(data, name=name, filename=self.filename,
                              options=options)
            out = hdf5storage.read(name=name, filename=self.filename,
                                   options=options)
        except:
            raise
        finally:
            if os.path.exists(self.filename):
                os.remove(self.filename)
        return out

    def assert_equal(self, a, b):
        # Compares a and b for equality. If they are not numpy types
        # (aren't or don't inherit from np.generic or np.ndarray), then
        # it is a matter of just comparing them. Otherwise, their dtypes
        # and shapes have to be compared. Then, if they are not an
        # object array, numpy.testing.assert_equal will compare them
        # elementwise. For object arrays, each element must be iterated
        # over to be compared.
        assert type(a) == type(b)
        if not isinstance(b, (np.generic, np.ndarray)):
            assert a == b
        else:
            assert a.dtype == b.dtype
            assert a.shape == b.shape
            if b.dtype.name != 'object':
                npt.assert_equal(a, b)
            else:
                for index, x in np.ndenumerate(a):
                    self.assert_equal(a[index], b[index])

    def assert_equal_python_collection(self, a, b, tp):
        # Compares two python collections that are supposed to be the
        # specified type tp. First, they have to be that type. If the
        # type is a set type, then a simple comparison is all that is
        # needed. Otherwise, an elementwise comparison needs to be done.
        assert type(a) == tp
        assert type(b) == tp
        assert len(a) == len(b)
        if type(b) in (set, frozenset):
            assert a == b
        else:
            for index in range(0, len(a)):
                self.assert_equal(a[index], b[index])

    def check_numpy_scalar(self, dtype):
        # Makes a random numpy scalar of the given type, writes it and
        # reads it back, and then compares it.
        data = self.random_numpy_scalar(dtype)
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        self.assert_equal(out, data)

    def check_numpy_array(self, dtype, dimensions):
        # Makes a random numpy array of the given type, writes it and
        # reads it back, and then compares it.
        shape = self.random_numpy_shape(dimensions,
                                        self.max_array_axis_length)
        data = self.random_numpy(shape, dtype)
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        self.assert_equal(out, data)

    def check_numpy_empty(self, dtype):
        # Makes an empty numpy array of the given type, writes it and
        # reads it back, and then compares it.
        data = np.array([], dtype)
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        self.assert_equal(out, data)

    def check_python_collection(self, tp):
        # Makes a random collection of the specified type, writes it and
        # reads it back, and then compares it.
        if tp in (set, frozenset):
            data = tp(self.random_list(self.max_list_length,
                      python_or_numpy='python'))
        else:
            data = tp(self.random_list(self.max_list_length,
                      python_or_numpy='numpy'))
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        self.assert_equal_python_collection(out, data, tp)

    def test_None(self):
        data = None
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        self.assert_equal(out, data)

    def test_bool_True(self):
        data = True
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        self.assert_equal(out, data)

    def test_bool_False(self):
        data = False
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        self.assert_equal(out, data)

    def test_int(self):
        data = self.random_int()
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        self.assert_equal(out, data)

    def test_float(self):
        data = self.random_float()
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        self.assert_equal(out, data)

    def test_float_inf(self):
        data = float(np.inf)
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        self.assert_equal(out, data)

    def test_float_ninf(self):
        data = float(-np.inf)
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        self.assert_equal(out, data)

    def test_float_nan(self):
        data = float(np.nan)
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        assert math.isnan(out)

    def test_complex(self):
        data = self.random_float() + 1j*self.random_float()
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        self.assert_equal(out, data)

    def test_complex_real_nan(self):
        data = complex(np.nan, self.random_float())
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        self.assert_equal(out, data)

    def test_complex_imaginary_nan(self):
        data = complex(self.random_float(), np.nan)
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        self.assert_equal(out, data)

    def test_str(self):
        data = self.random_str_ascii(random.randint(1,
                                     self.max_string_length))
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        self.assert_equal(out, data)

    def test_str_empty(self):
        data = ''
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        self.assert_equal(out, data)

    def test_bytes(self):
        data = self.random_bytes(random.randint(1,
                                 self.max_string_length))
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        self.assert_equal(out, data)

    def test_bytes_empty(self):
        data = b''
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        self.assert_equal(out, data)

    def test_bytearray(self):
        data = bytearray(self.random_bytes(random.randint(1,
                         self.max_string_length)))
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        self.assert_equal(out, data)

    def test_bytearray_empty(self):
        data = bytearray(b'')
        out = self.write_readback(data, self.random_name(),
                                  self.options)
        self.assert_equal(out, data)

    def test_numpy_scalar(self):
        for dt in self.dtypes:
            yield self.check_numpy_scalar, dt

    def test_numpy_array_1d(self):
        dtypes = self.dtypes.copy()
        dtypes.append('object')
        for dt in dtypes:
            yield self.check_numpy_array, dt, 1

    def test_numpy_array_2d(self):
        dtypes = self.dtypes.copy()
        dtypes.append('object')
        for dt in dtypes:
            yield self.check_numpy_array, dt, 2

    def test_numpy_array_3d(self):
        dtypes = self.dtypes.copy()
        dtypes.append('object')
        for dt in dtypes:
            yield self.check_numpy_array, dt, 3

    def test_numpy_empty(self):
        for dt in self.dtypes:
            yield self.check_numpy_empty, dt

    def test_python_collection(self):
        for tp in (list, tuple, set, frozenset, collections.deque):
            yield self.check_python_collection, tp


class TestPythonFormat(TestPythonMatlabFormat):
    def __init__(self):
        # The parent does most of the setup. All that has to be changed
        # is turning MATLAB compatibility off and changing the file
        # name.
        TestPythonMatlabFormat.__init__(self)
        self.options = hdf5storage.Options(matlab_compatible=False)
        self.filename = 'data.h5'


class TestNoneFormat(TestPythonMatlabFormat):
    def __init__(self):
        # The parent does most of the setup. All that has to be changed
        # is turning off the storage of type information as well as
        # MATLAB compatibility.
        TestPythonMatlabFormat.__init__(self)
        self.options = hdf5storage.Options(store_type_information=False,
                                           matlab_compatible=False)

    def assert_equal(self, a, b):
        # Compares a and b for equality. b is always the original. If
        # the original is not a numpy type (isn't or doesn't inherit
        # from np.generic or np.ndarray), then it is a matter of
        # converting it to the appropriate numpy type. Otherwise, both
        # are supposed to be numpy types. For object arrays, each
        # element must be iterated over to be compared. Then, if it
        # isn't a string type, then they must have the same dtype,
        # shape, and all elements. If it is an empty string, then it
        # would have been stored as just a null byte (recurse to do that
        # comparison). If it is a bytes_ type, the dtype, shape, and
        # elements must all be the same. If it is string_ type, we must
        # convert to uint32 and then everything can be compared.
        if not isinstance(b, (np.generic, np.ndarray)):
            if b is None:
                # It should be np.float64([])
                assert type(a) == np.ndarray
                assert a.dtype == np.float64([]).dtype
                assert a.shape == (0, )
            elif isinstance(b, (bytes, str, bytearray)):
                assert a == np.bytes_(b)
            else:
                self.assert_equal(a, \
                    np.array(b)[()])
        else:
            if b.dtype.name != 'object':
                if b.dtype.char in ('U', 'S'):
                    if b.shape == tuple() and len(b) == 0:
                        self.assert_equal(a, \
                            np.zeros(shape=tuple(), dtype=b.dtype.char))
                    elif b.dtype.char == 'U':
                        c = np.atleast_1d(b).view(np.uint32)
                        assert a.dtype == c.dtype
                        assert a.shape == c.shape
                        npt.assert_equal(a, c)
                    else:
                        assert a.dtype == b.dtype
                        assert a.shape == b.shape
                        npt.assert_equal(a, b)
                else:
                    assert a.dtype == b.dtype
                    assert a.shape == b.shape
                    npt.assert_equal(a, b)
            else:
                assert a.dtype == b.dtype
                assert a.shape == b.shape
                for index, x in np.ndenumerate(a):
                    self.assert_equal(a[index], b[index])

    def assert_equal_python_collection(self, a, b, tp):
        # Compares two python collections that are supposed to be the
        # specified type tp. As every collection is just getting turned
        # into a list and then a numpy object array, b must be converted
        # first before the comparison.
        c = np.object_(list(b))
        self.assert_equal(a, c)


class TestMatlabFormat(TestNoneFormat):
    def __init__(self):
        # The parent does most of the setup. All that has to be changed
        # is turning on the matlab compatibility, changing the filename,
        # and removing 'float16' from the dtype list (its not supported
        # by matlab).
        TestNoneFormat.__init__(self)
        self.options = hdf5storage.Options(store_type_information=False,
                                           matlab_compatible=True)
        self.filename = 'data.mat'
        self.dtypes.remove('float16')

    def assert_equal(self, a, b):
        # Compares a and b for equality. b is always the original. If
        # the original is not a numpy type (isn't or doesn't inherit
        # from np.generic or np.ndarray), then it is a matter of
        # converting it to the appropriate numpy type. Otherwise, both
        # are supposed to be numpy types. For object arrays, each
        # element must be iterated over to be compared. Then, if it
        # isn't a string type, then they must have the same dtype,
        # shape, and all elements. All strings are converted to
        # numpy.str_ on read. If it is empty, it has shape (1, 0). A
        # numpy.str_ has all of its strings per row compacted
        # together. A numpy.bytes_ string has to have the same thing
        # done, but then it needs to be converted up to UTF-32 and to
        # numpy.str_ through uint32.
        #
        # In all cases, we expect things to be at least two dimensional
        # arrays.
        if not isinstance(b, (np.generic, np.ndarray)):
            if b is None:
                # It should be np.zeros(shape=(0, 1), dtype='float64'))
                assert type(a) == np.ndarray
                assert a.dtype == np.dtype('float64')
                assert a.shape == (1, 0)
            elif isinstance(b, (bytes, str, bytearray)):
                if len(b) == 0:
                    TestPythonMatlabFormat.assert_equal(self, a, \
                        np.zeros(shape=(1, 0), dtype='U'))
                elif isinstance(b, (bytes, bytearray)):
                    TestPythonMatlabFormat.assert_equal(self, a, \
                        np.atleast_2d(np.str_(b.decode())))
                else:
                    TestPythonMatlabFormat.assert_equal(self, a, \
                        np.atleast_2d(np.str_(b)))
            else:
                TestPythonMatlabFormat.assert_equal(self, a, \
                    np.atleast_2d(np.array(b)))
        else:
            if b.dtype.name != 'object':
                if b.dtype.char in ('U', 'S'):
                    if len(b) == 0 and (b.shape == tuple() \
                            or b.shape == (0, )):
                        TestPythonMatlabFormat.assert_equal(self, a, \
                            np.zeros(shape=(1, 0), \
                            dtype='U'))
                    elif b.dtype.char == 'U':
                        c = np.atleast_1d(b)
                        c = np.atleast_2d(c.view(np.dtype('U' \
                            + str(c.shape[-1]*c.dtype.itemsize//4))))
                        assert a.dtype == c.dtype
                        assert a.shape == c.shape
                        npt.assert_equal(a, c)
                    elif b.dtype.char == 'S':
                        c = np.atleast_1d(b)
                        c = c.view(np.dtype('S' \
                            + str(c.shape[-1]*c.dtype.itemsize)))
                        c = np.uint32(c.view(np.dtype('uint8')))
                        c = c.view(np.dtype('U' + str(c.shape[-1])))
                        c = np.atleast_2d(c)
                        assert a.dtype == c.dtype
                        assert a.shape == c.shape
                        npt.assert_equal(a, c)
                        pass
                    else:
                        c = np.atleast_2d(b)
                        assert a.dtype == c.dtype
                        assert a.shape == c.shape
                        npt.assert_equal(a, c)
                else:
                    c = np.atleast_2d(b)
                    # An empty complex number gets turned into a real
                    # number when it is stored.
                    if np.prod(c.shape) == 0 \
                            and b.dtype.name.startswith('complex'):
                        c = np.real(c)
                    assert a.dtype == c.dtype
                    assert a.shape == c.shape
                    npt.assert_equal(a, c)
            else:
                c = np.atleast_2d(b)
                assert a.dtype == c.dtype
                assert a.shape == c.shape
                for index, x in np.ndenumerate(a):
                    self.assert_equal(a[index], c[index])