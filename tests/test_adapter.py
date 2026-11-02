"""Tests for VariableFanOutAdapter.invoke."""

from datetime import UTC, datetime
from unittest.mock import patch

import numpy as np
import pytest
import xarray as xr
from harmony_service_lib.message import Message
from pystac import Asset, Catalog, Item

from variable_fan_out.adapter import VariableFanOutAdapter


@pytest.fixture
def two_variable_netcdf_file(tmp_path):
    """A netCDF file with two variables net2cog will find.

    Test fixture used that returns two net2cog griddable variables. "var1" and
    "var2"
    """
    path = tmp_path / "variable_file.nc"
    xr.Dataset(
        {
            "var1": (("lat", "lon"), np.zeros((10, 20))),
            "var2": (("lat", "lon"), np.zeros((10, 20))),
            "ungriddable-var": (("time"), np.zeros((10,))),
        }
    ).to_netcdf(path)
    return str(path)


@pytest.fixture
def no_spatial_dims_file(tmp_path):
    """A netCDF file that net2cog finds no variables in.

    This fixture is a file that net2cog will find no griddable variables in.

    """
    path = tmp_path / "no_spatial_dims.nc"
    xr.Dataset({"var3": (("a", "b"), np.zeros((10, 20)))}).to_netcdf(path)
    return str(path)


def make_harmony_message(variables=None):
    """Return a harmony message who's source may or may not have explicit variables.

    If called with a variables keyword the Harmony Message will have explicit variables.
    """
    source = {
        "collection": "C123456789-TEST",
        "shortName": "Testname",
        "versionId": "1",
    }
    if variables:
        source["variables"] = [
            {"id": f"Var{i}", "name": v, "fullPath": v} for i, v in enumerate(variables)
        ]
    return Message({"sources": [source]})


def make_catalog(item_ids: list[str]):
    """STAC catalog fixture.

    Creates a stac catalog with item_ids for items. Mostly used to Initialize a
    VariableFanOutAdapter, but there is a test to verify handling of the
    uncommon (impossible?) case of multiple items.

    """
    catalog = Catalog(id="input-catalog", description="test input catalog")
    for item_id in item_ids:
        item = Item(
            id=item_id,
            geometry=None,
            bbox=None,
            datetime=datetime.now(tz=UTC),
            properties={},
        )
        item.add_asset(
            "data", Asset(href=f"https://example.com/{item_id}.nc", roles=["data"])
        )
        catalog.add_item(item)
    return catalog


def test_fans_out_one_catalog_per_variable(two_variable_netcdf_file):
    """A single item catalog with a netcdf_file containing two variables
    creates a catalog for each of the files variables.
    """

    catalog = make_catalog(["granule"])
    harmony_message_with_no_variables = make_harmony_message()

    with patch(
        "variable_fan_out.adapter.download", return_value=two_variable_netcdf_file
    ):
        _, output_catalogs = VariableFanOutAdapter(
            harmony_message_with_no_variables, catalog
        ).invoke()

    # the output catalogs each have one item and contain the variable on the
    # item's special property.
    for c, expected_var in zip(output_catalogs, ["/var1", "/var2"], strict=True):
        items = list(c.get_items())
        assert len(items) == 1
        assert items[0].properties["harmony:variable"] == expected_var

    # input catalog unchanged.
    assert "harmony:variable" not in next(catalog.get_items("granule")).properties


def test_explicit_variables_return_input_catalog():
    """A single item catalog with a netcdf_file containing two variables and a
    Harmony Message with explicit variables returns the input catalog without
    downloading the input item's file.
    """
    catalog = make_catalog(["granule"])
    message_with_explicit_vars = make_harmony_message(variables=["var4", "var5"])

    with patch("variable_fan_out.adapter.download") as download:
        _, output_catalog = VariableFanOutAdapter(
            message_with_explicit_vars, catalog
        ).invoke()

    assert output_catalog is catalog
    download.assert_not_called()


def test_disabled_env_returns_input_catalog(monkeypatch):
    """Verify environmental override prevents fanout behavior.
    Input catalog is unchanged, download is not called.

    Same test as test_fans_out_one_catalog_per_variable with environmental
    override.
    """
    monkeypatch.setenv("HARMONY_VARIABLE_FAN_OUT_ENABLED", "false")
    catalog = make_catalog(["granule"])
    harmony_message_with_no_variables = make_harmony_message()

    with patch("variable_fan_out.adapter.download") as download:
        _, output_catalog = VariableFanOutAdapter(
            harmony_message_with_no_variables, catalog
        ).invoke()

    assert output_catalog is catalog
    download.assert_not_called()


def test_download_error_retuns_input_catalog():
    catalog = make_catalog(["granule"])

    with patch("variable_fan_out.adapter.download", side_effect=Exception("Forbidden")):
        _, output = VariableFanOutAdapter(make_harmony_message(), catalog).invoke()

    assert output is catalog


def test_item_without_variables_is_passed_through_unchanged(
    two_variable_netcdf_file, no_spatial_dims_file
):
    """Test a multi-item catalog with two Items that have discoverable
    variables and one that does not.

    This is an unlikely scenario, but we don't want to drop the Item without
    discoverable variables, it should be passed unchanged to net2cog and we let
    it fail there.

    """
    catalog = make_catalog(["has-vars", "no-vars", "has-vars2"])

    def fake_download(href, *args, **kwargs):
        return no_spatial_dims_file if "no-vars" in href else two_variable_netcdf_file

    with patch("variable_fan_out.adapter.download", side_effect=fake_download):
        _, output_catalogs = VariableFanOutAdapter(
            make_harmony_message(), catalog
        ).invoke()

    # We're checking the ids of the Items to see which catalogs are
    # returned. The Items with variables are duplicated for each var, the other
    # is not.
    expected_ids = [
        "has-vars-var-1",
        "has-vars-var-2",
        "no-vars",
        "has-vars2-var-1",
        "has-vars2-var-2",
    ]

    for c, expected_id in zip(output_catalogs, expected_ids, strict=True):
        items = list(c.get_items())
        assert len(items) == 1
        assert items[0].id == expected_id

    # assert the no_vars catalog (the third) wasn't amended.
    no_vars_item = next(output_catalogs[2].get_items())
    assert "harmony:variable" not in no_vars_item.properties
