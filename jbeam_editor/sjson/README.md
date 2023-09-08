SJSON
=====

**SJSON** is a small library to read/write simplified JSON, as described originally on the [Bitsquid blog](http://bitsquid.blogspot.de/2009/10/simplified-json-notation.html).

License
-------

**SJSON** is licensed under the two-clause BSD license. See `LICENSE.txt` for details.

SJSON format
------------

SJSON is very similar to normal JSON (in fact, since release 1.2.0, the SJSON library will also load plain JSON). It mostly reduces the required markup a bit. The main differences are:

* Every file starts with an implicit object. That is, an empty SJSON file is equivalent to a JSON file containing `{}`.
* Commas after a key-value pair are optional.
* Keys don't have to be quoted as long as they are valid identifiers. An identifier consists of letters, digits, and `_`.
* `=` is allowed in addition to `:` for key-value separation. The canonical separator is `=`.
* C and C++ style comments are allowed.

In addition, this library provides support for raw string literals.

Example
-------

JSON:

    {
        "foo" : 23,
        "bar" : [1, 2, 3],
        "baz" : {
            "key" : "value"
        }
    }

SJSON:

    foo = 23
    bar = [1, 2, 3]
    baz = {
        // SJSON also allows for comments
        key = "value"
    }

As an extension, SJSON allows for raw string literals, in both Lua and Python flavors:

    foo = [=[This is a raw literal with embedded " and stuff]=]

    foo = """This is a raw literal with embedded " and stuff"""

Usage
-----

The library provides four methods, similar to the Python JSON module. These are:

* `dump`: Encode an object as SJSON and write to a stream.
* `dumps`: Encode an object as SJSON and return a string.
* `load`: Decode a SJSON encoded object from a stream.
* `loads`: Decode a SJSON encoded object from a string.

Changelog
---------

### 2.1

* Add support for Python-style raw strings, delimited by `"""`.
* Improve handling of unknown string escapes. Previously, those would raise an exception, now they get passed through.

### 2.0.3

* Re-release of 2.0.2.

### 2.0.2

* Packaging changes only. This release contains packaging changes only and has not been released to the public, use 2.0.3 instead.

### 2.0.1

* Add `dump` in addition to `dumps` for consistency with the Python JSON module.
* Additional PEP8 conformance tweaks.

### 2.0.0

* The library is now PEP8 compliant. This should *not* affect most users of this library, the only user-visible change is that `ParseException.GetLocation` has been renamed to `get_location`. The core functions have not been renamed and are API compatible.

### 1.2.0

* Keys did not get quoted properly during encoding if they contained special characters.
* List elements were incorrectly indented.
* List indentation now accepts either a string or a number (similar to the Python JSON module.)
* Both `:` and `=` are now supported as key-value separators, allowing the SJSON library to parse plain JSON files.

### 1.1.1

* Add support for C/C++ style comments.
* Line/column numbers start at 1 now (previously, the first character was in line 0, column 0).

### 1.1.0

* Parsing performance has been significantly improved.
* It is possible to parse a file-like stream or string now.

### 1.0.4

* Track position during parsing. This will likely reduce the performance a bit, but allows for much better error messages.
* Input is byte-oriented now.

### 1.0.3

* Add support for raw string literals. These are delimited by `[=[` `]=]` and don't require escaping inside the string.

### 1.0.2

* Strings with whitespace are now properly escaped.

### 1.0.1

* Various fixes to string encoding/decoding bugs.
* Encoding now uses `collections.abc` to identify sequences and mappings instead of testing directly against `list` and `dict`.

### 1.0.0

Initial PyPI release.
