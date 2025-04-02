import os
from pathlib import Path
from typing import AsyncGenerator, Generator, List, Literal

import adbc_driver_postgresql
import adbc_driver_sqlite
import numpy
import pyarrow as pa
import pytest
import pytest_asyncio

from tiled._tests.utils import temp_postgres
from tiled.adapters.sql import (
    arrow_schema_to_column_defns,
    arrow_schema_to_create_table,
    create_connection,
)


@pytest_asyncio.fixture
async def postgresql_uri() -> AsyncGenerator[str, None]:
    uri = os.getenv("TILED_TEST_POSTGRESQL_URI")
    if uri is None:
        pytest.skip("TILED_TEST_POSTGRESQL_URI is not set")

    async with temp_postgres(uri) as uri_with_database_name:
        yield uri_with_database_name
        # yield uri_with_database_name.rsplit("/", 1)[0]


@pytest_asyncio.fixture
def sqlite_uri(tmp_path: Path) -> Generator[str, None, None]:
    yield f"sqlite:///{tmp_path}/test.db"


@pytest_asyncio.fixture
def duckdb_uri(tmp_path: Path) -> Generator[str, None, None]:
    yield f"duckdb:///{tmp_path}/test.db"


# parameters from duckdb test
[
    (
        pa.schema([("some_float16", "float16")]),
        pa.schema([("some_float16", "float32")]),
        ["REAL NULL"],
    ),
    (
        pa.schema([("some_float32", "float32")]),
        pa.schema([("some_float32", "float32")]),
        ["REAL NULL"],
    ),
    (
        pa.schema([("some_float64", "float64")]),
        pa.schema([("some_float64", "float64")]),
        ["DOUBLE NULL"],
    ),
    (
        pa.schema([("some_string", "string")]),
        pa.schema([("some_string", "string")]),
        ["VARCHAR NULL"],
    ),
    (
        pa.schema([("some_large_string", pa.large_string())]),
        pa.schema([("some_large_string", "string")]),
        ["VARCHAR NULL"],
    ),
    (
        pa.schema([("some_integer_array", pa.list_(pa.int32()))]),
        pa.schema([("some_integer_array", pa.list_(pa.int32()))]),
        ["INTEGER[] NULL"],
    ),
    (
        pa.schema([("some_large_integer_array", pa.list_(pa.int64()))]),
        pa.schema([("some_large_integer_array", pa.list_(pa.int64()))]),
        ["BIGINT[] NULL"],
    ),
    (
        pa.schema([("some_fixed_size_integer_array", pa.list_(pa.int64(), 2))]),
        pa.schema([("some_fixed_size_integer_array", pa.list_(pa.int64()))]),
        ["BIGINT[] NULL"],
    ),
    (
        pa.schema([("some_decimal", pa.decimal128(precision=38, scale=9))]),
        pa.schema([("some_decimal", pa.decimal128(precision=38, scale=9))]),
        ["DECIMAL(38, 9) NULL"],
    ),
],

INT8_INFO = numpy.iinfo(numpy.int8)
INT16_INFO = numpy.iinfo(numpy.int16)
INT32_INFO = numpy.iinfo(numpy.int32)
INT64_INFO = numpy.iinfo(numpy.int64)
UINT8_INFO = numpy.iinfo(numpy.uint8)
UINT16_INFO = numpy.iinfo(numpy.uint16)
UINT32_INFO = numpy.iinfo(numpy.uint32)
UINT64_INFO = numpy.iinfo(numpy.uint64)
# Map schemas (testing different data types or combinations of data types)
# to an inner mapping. The inner mapping maps each dialect to a tuple,
# (SQL type definition, Arrow type read back).
TEST_CASES = {
    "bool": (
        pa.Table.from_arrays([pa.array([True, False], "bool")], names=["x"]),
        {
            "duckdb": (["BOOLEAN NULL"], pa.schema([("x", "bool")])),
            "sqlite": (["INTEGER NULL"], pa.schema([("x", "int64")])),
            "postgresql": (["BOOLEAN NULL"], pa.schema([("x", "bool")])),
        },
    ),
    "string": (
        pa.Table.from_arrays([pa.array(["a", "b"], "string")], names=["x"]),
        {
            "duckdb": (["VARCHAR NULL"], pa.schema([("x", "string")])),
            "sqlite": (["TEXT NULL"], pa.schema([("x", "string")])),
            "postgresql": (["TEXT NULL"], pa.schema([("x", "string")])),
        },
    ),
    "int8": (
        pa.Table.from_arrays(
            [pa.array([INT8_INFO.min, INT8_INFO.max], "int8")], names=["x"]
        ),
        {
            "duckdb": (["TINYINT NULL"], pa.schema([("x", "int8")])),
            "sqlite": (["INTEGER NULL"], pa.schema([("x", "int64")])),
            "postgresql": (["SMALLINT NULL"], pa.schema([("x", "int16")])),
        },
    ),
    "int16": (
        pa.Table.from_arrays(
            [pa.array([INT16_INFO.min, INT16_INFO.max], "int16")], names=["x"]
        ),
        {
            "duckdb": (["SMALLINT NULL"], pa.schema([("x", "int16")])),
            "sqlite": (["INTEGER NULL"], pa.schema([("x", "int64")])),
            "postgresql": (["SMALLINT NULL"], pa.schema([("x", "int16")])),
        },
    ),
    "int32": (
        pa.Table.from_arrays(
            [pa.array([INT32_INFO.min, INT32_INFO.max], "int32")], names=["x"]
        ),
        {
            "duckdb": (["INTEGER NULL"], pa.schema([("x", "int32")])),
            "sqlite": (["INTEGER NULL"], pa.schema([("x", "int64")])),
            "postgresql": (["INTEGER NULL"], pa.schema([("x", "int32")])),
        },
    ),
    "int64": (
        pa.Table.from_arrays(
            [pa.array([INT64_INFO.min, INT64_INFO.max], "int64")], names=["x"]
        ),
        {
            "duckdb": (["BIGINT NULL"], pa.schema([("x", "int64")])),
            "sqlite": (["INTEGER NULL"], pa.schema([("x", "int64")])),
            "postgresql": (["BIGINT NULL"], pa.schema([("x", "int64")])),
        },
    ),
    "uint8": (
        pa.Table.from_arrays(
            [pa.array([UINT8_INFO.min, UINT8_INFO.max], "uint8")], names=["x"]
        ),
        {
            "duckdb": (["UTINYINT NULL"], pa.schema([("x", "uint8")])),
            "sqlite": (["INTEGER NULL"], pa.schema([("x", "int64")])),
            "postgresql": (["SMALLINT NULL"], pa.schema([("x", "int16")])),
        },
    ),
    "uint16": (
        pa.Table.from_arrays(
            [pa.array([UINT16_INFO.min, UINT16_INFO.max], "uint16")], names=["x"]
        ),
        {
            "duckdb": (["USMALLINT NULL"], pa.schema([("x", "uint16")])),
            "sqlite": (["INTEGER NULL"], pa.schema([("x", "int64")])),
            "postgresql": (["INTEGER NULL"], pa.schema([("x", "int32")])),
        },
    ),
    "uint32": (
        pa.Table.from_arrays(
            [pa.array([UINT32_INFO.min, UINT32_INFO.max], "uint32")], names=["x"]
        ),
        {
            "duckdb": (["UINTEGER NULL"], pa.schema([("x", "uint32")])),
            "sqlite": (["INTEGER NULL"], pa.schema([("x", "int64")])),
            "postgresql": (["BIGINT NULL"], pa.schema([("x", "int64")])),
        },
    ),
    "uint64": (
        pa.Table.from_arrays(
            [pa.array([UINT64_INFO.min, UINT64_INFO.max], "uint64")], names=["x"]
        ),
        {
            "duckdb": (["UBIGINT NULL"], pa.schema([("x", "uint64")])),
        },
    ),
    "list_of_ints": (
        pa.Table.from_arrays(
            [pa.array([[1, 2], [3, 4]], pa.list_(pa.int32()))], names=["x"]
        ),
        {
            "duckdb": (["INTEGER[] NULL"], pa.schema([("x", pa.list_(pa.int32()))])),
            "postgresql": (
                ["INTEGER ARRAY NULL"],
                pa.schema([("x", pa.list_(pa.int32()))]),
            ),
        },
    ),
}


@pytest.mark.parametrize("dialect", ["duckdb", "postgresql", "sqlite"])
@pytest.mark.parametrize("test_case_id", list(TEST_CASES))
def test_data_types(
    test_case_id: str,
    dialect: Literal["postgresql", "sqlite", "duckdb"],
    request: pytest.FixtureRequest,
) -> None:
    table, dialect_results = TEST_CASES[test_case_id]
    if dialect not in dialect_results:
        with pytest.raises(ValueError, match="Unsupported PyArrow type"):
            arrow_schema_to_column_defns(table.schema, dialect)
        return

    expected_typedefs, expected_schema = dialect_results[dialect]
    db_uri = request.getfixturevalue(f"{dialect}_uri")
    columns = arrow_schema_to_column_defns(table.schema, dialect)
    assert list(columns.values()) == expected_typedefs

    query = arrow_schema_to_create_table(table.schema, "random_test_table", dialect)

    with create_connection(db_uri) as conn:
        with conn.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS random_test_table")
            cursor.execute(query)
        conn.commit()

        # For SQLite specifically, some inference is needed by ADBC to get the type
        # and on an empty table the value is not defined. As of this writing it is
        # int64 by default; in the future it may be null.
        # https://github.com/apache/arrow-adbc/issues/581
        if dialect != "sqlite":
            assert conn.adbc_get_table_schema("random_test_table") == expected_schema

        with conn.cursor() as cursor:
            cursor.adbc_ingest("random_test_table", table, mode="append")

        assert conn.adbc_get_table_schema("random_test_table") == expected_schema

        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM random_test_table")
            result = cursor.fetch_arrow_table()

        # The result will match expected_schema, which may not be the same as
        # the schema the data was uploaded as, if the databases does not support
        # that precise type.
        assert result.schema == expected_schema

        # Before comparing the Tables, we cast the Table into the original schema,
        # which might use finer types.
        assert result.cast(table.schema) == table


@pytest.mark.parametrize(
    "actual_schema, expected_schema, expected_keywords",
    [
        (
            pa.schema([("some_bool", pa.bool_())]),
            pa.schema([("some_bool", "bool")]),
            ["BOOLEAN"],
        ),
        (
            pa.schema([("some_int8", pa.int8())]),
            pa.schema([("some_int8", "int16")]),
            ["SMALLINT"],
        ),
        (
            pa.schema([("some_uint8", pa.uint8())]),
            pa.schema([("some_uint8", "int16")]),
            ["SMALLINT"],
        ),
        (
            pa.schema([("some_int16", pa.int16())]),
            pa.schema([("some_int16", "int16")]),
            ["SMALLINT"],
        ),
        (
            pa.schema([("some_uint16", pa.uint16())]),
            pa.schema([("some_uint16", "int16")]),
            ["SMALLINT"],
        ),
        (
            pa.schema([("some_int32", pa.int32())]),
            pa.schema([("some_int32", "int32")]),
            ["INTEGER"],
        ),
        (
            pa.schema([("some_uint32", pa.uint32())]),
            pa.schema([("some_uint32", "int32")]),
            ["INTEGER"],
        ),
        (
            pa.schema([("some_int64", pa.int64())]),
            pa.schema([("some_int64", "int64")]),
            ["BIGINT"],
        ),
        (
            pa.schema([("some_uint64", pa.uint64())]),
            pa.schema([("some_uint64", "int64")]),
            ["BIGINT"],
        ),
        (
            pa.schema([("some_float16", pa.float16())]),
            pa.schema([("some_float16", "float")]),
            ["REAL"],
        ),
        (
            pa.schema([("some_float32", pa.float32())]),
            pa.schema([("some_float32", "float")]),
            ["REAL"],
        ),
        (
            pa.schema([("some_float64", pa.float64())]),
            pa.schema([("some_float64", "double")]),
            ["DOUBLE PRECISION"],
        ),
        (
            pa.schema([("some_string", pa.string())]),
            pa.schema([("some_string", "string")]),
            ["TEXT"],
        ),
        (
            pa.schema([("some_large_string", pa.large_string())]),
            pa.schema([("some_large_string", "string")]),
            ["TEXT"],
        ),
        (
            pa.schema([("some_integer_array", pa.list_(pa.int32()))]),
            pa.schema([("some_integer_array", pa.list_(pa.int32()))]),
            ["INTEGER ARRAY"],
        ),
        (
            pa.schema([("some_large_integer_array", pa.list_(pa.int64()))]),
            pa.schema([("some_large_integer_array", pa.list_(pa.int64()))]),
            ["BIGINT ARRAY"],
        ),
        (
            pa.schema([("some_fixed_size_integer_array", pa.list_(pa.int64(), 2))]),
            pa.schema([("some_fixed_size_integer_array", pa.list_(pa.int64()))]),
            ["BIGINT ARRAY"],
        ),
    ],
)
def test_psql_data_types(
    actual_schema: pa.Schema,
    expected_schema: pa.Schema,
    expected_keywords: List[str],
    postgres_uri: str,
) -> None:
    query = arrow_schema_to_create_table(
        actual_schema, "random_test_table", "postgresql"
    )

    for keyword in expected_keywords:
        assert keyword in query

    conn = create_connection(postgres_uri)
    assert isinstance(conn, adbc_driver_postgresql.dbapi.Connection)

    with conn.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS random_test_table")
        cursor.execute(query)
    conn.commit()

    assert conn.adbc_get_table_schema("random_test_table") == expected_schema

    conn.close()


@pytest.mark.parametrize(
    "actual_schema, expected_schema, expected_keywords",
    [
        (
            pa.schema([("some_bool", pa.bool_())]),
            pa.schema([("some_bool", "int64")]),
            ["INTEGER"],
        ),
        (
            pa.schema([("some_int8", pa.int8())]),
            pa.schema([("some_int8", "int64")]),
            ["INTEGER"],
        ),
        (
            pa.schema([("some_uint8", pa.uint8())]),
            pa.schema([("some_uint8", "int64")]),
            ["INTEGER"],
        ),
        (
            pa.schema([("some_int16", pa.int16())]),
            pa.schema([("some_int16", "int64")]),
            ["INTEGER"],
        ),
        (
            pa.schema([("some_uint16", pa.uint16())]),
            pa.schema([("some_uint16", "int64")]),
            ["INTEGER"],
        ),
        (
            pa.schema([("some_int32", pa.int32())]),
            pa.schema([("some_int32", "int64")]),
            ["INTEGER"],
        ),
        (
            pa.schema([("some_uint32", pa.uint32())]),
            pa.schema([("some_uint32", "int64")]),
            ["INTEGER"],
        ),
        (
            pa.schema([("some_int64", pa.int64())]),
            pa.schema([("some_int64", "int64")]),
            ["INTEGER"],
        ),
        (
            pa.schema([("some_uint64", pa.uint64())]),
            pa.schema([("some_uint64", "int64")]),
            ["INTEGER"],
        ),
        (
            pa.schema([("some_float16", pa.float16())]),
            pa.schema([("some_float16", "int64")]),
            ["REAL"],
        ),
        (
            pa.schema([("some_float32", pa.float32())]),
            pa.schema([("some_float32", "int64")]),
            ["REAL"],
        ),
        (
            pa.schema([("some_float64", pa.float64())]),
            pa.schema([("some_float64", "int64")]),
            ["REAL"],
        ),
        (
            pa.schema([("some_string", pa.string())]),
            pa.schema([("some_string", "int64")]),
            ["TEXT"],
        ),
        (
            pa.schema([("some_large_string", pa.large_string())]),
            pa.schema([("some_large_string", "int64")]),
            ["TEXT"],
        ),
        (
            pa.schema([("some_integer_array", pa.list_(pa.int32()))]),
            pa.schema([("some_integer_array", "int64")]),
            ["TEXT"],
        ),
        (
            pa.schema([("some_large_integer_array", pa.list_(pa.int64()))]),
            pa.schema([("some_large_integer_array", "int64")]),
            ["TEXT"],
        ),
        (
            pa.schema([("some_fixed_size_integer_array", pa.list_(pa.int64(), 2))]),
            pa.schema([("some_fixed_size_integer_array", "int64")]),
            ["TEXT"],
        ),
    ],
)
def test_sqlite_data_types(
    actual_schema: pa.Schema,
    expected_schema: pa.Schema,
    expected_keywords: List[str],
    sqlite_uri: str,
) -> None:
    query = arrow_schema_to_create_table(actual_schema, "random_test_table", "sqlite")

    for keyword in expected_keywords:
        assert keyword in query

    conn = create_connection(sqlite_uri)
    assert isinstance(conn, adbc_driver_sqlite.dbapi.Connection)

    with conn.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS random_test_table")
        cursor.execute(query)
    conn.commit()

    # !!!!!BIG BIG WARNING!!!
    # For some weird reason `adbc_get_table_schema` reads everything as `int64`
    # Not sure it is a bug but but be aware!!!!!!
    assert conn.adbc_get_table_schema("random_test_table") == expected_schema

    conn.close()
