# Service to fan out all variables in a file
from __future__ import annotations

import os
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import xarray as xr
from harmony_service_lib import BaseHarmonyAdapter
from harmony_service_lib.util import download
from net2cog.netcdf_convert import get_all_data_variables
from pystac import Catalog, Item

if TYPE_CHECKING:
    from harmony_service_lib.message import Message


class VariableFanOutAdapter(BaseHarmonyAdapter):
    """
    See See https://github.com/nasa/harmony-service-lib-py
    for documentation and examples.
    """

    def invoke(self) -> tuple[Message, Catalog | list[Catalog]]:
        """Writes a catalog per (item, variable) when no explicit vars are requested.

        The variable fan out service processes the incoming
        ``Harmony.message``.  It checks to see if there are any explicitly
        defined variables in the message's source and if so, passes the message
        along as a no-op to the next service in the chain [net2cog].

        If the incoming message has not explicitly asked for variables from
        the file, this routine downloads each Item's data asset and generates
        its list of variables using net2cogs get_all_data_variables routine
        directly.  [Generally (always?) there will be one Item per Catalog.]

        For every item and every variable it writes a catalog containing the
        variable's name added to the item's properties as ``harmony:variable``.

        An Item whose data file returns no variables gets a catalog holding
        just a clone of the item, so the downstream service sees the item and
        fails (net2cog will also find no variables in the file).

        Harmony will then call the downstream service, net2cog, with each of
        the catalogs in parallel fanning out to num-of-variables pods per item.

        Any errors raised are caught, logged, and then the original input
        message and catalog are returned to Harmony.

        If the environment variable ``VARIABLE_FAN_OUT_DISABLED`` is ``true``
        the input message and catalog are returned unchanged.  Harmony's
        local Harmony-In-A-Box defaults it to ``true`` so the fan out is
        skipped locally without changing the chain..

        Returns a tuple of the input Message and either the input Catalog (on
        error or explicit variables requested), or a list of catalogs, one per
        item/variable pair, each containing a single item from the input
        catalog amended with one of its variables.

        """
        if not self.catalog:
            raise RuntimeError(
                "The variable fan out service requires an input STAC catalog."
            )

        if os.environ.get("VARIABLE_FAN_OUT_DISABLED", "").lower() == "true":
            self.logger.info(
                "VARIABLE_FAN_OUT_DISABLED is true; exiting without creating fan out catalogs"
            )
            return (self.message, self.catalog)

        try:
            if any(source.variables for source in self.message.sources):
                self.logger.info(
                    "explicit variables requested; exiting without creating fan out catalogs"
                )
                return (self.message, self.catalog)

            # Discover each Item's own variables and clone a catalog for every
            # variable in the Item's href
            catalogs = []
            for item in self.catalog.get_items():
                asset = next(
                    v for v in item.assets.values() if "data" in (v.roles or [])
                )
                href = asset.href
                self.logger.info(f"Discovered href: {href}")
                with TemporaryDirectory() as tmpdir:
                    input_filename = download(
                        href,
                        tmpdir,
                        logger=self.logger,
                        access_token=self.message.accessToken,
                        cfg=self.config,
                    )
                    with xr.open_datatree(
                        input_filename,
                        decode_coords=False,
                        decode_times=False,
                        decode_timedelta=False,
                        concat_characters=True,
                    ) as input_datatree:
                        var_list = get_all_data_variables(input_datatree, self.logger)

                # If we don't discover any variables, we add this Item alone to
                # a catalog, for the unlikely case of multiple items, we don't
                # want to just pass on the original catalog in case we can
                # still process the second item. (rather than just returning
                # the input catalog)
                if not var_list:
                    self.logger.info(
                        f"No variables found for item {item.id}; passing it through unchanged"
                    )
                    catalog = self.catalog.clone()
                    catalog.id = f"{self.catalog.id}-{item.id}"
                    catalog.remove_links(rel="item")
                    catalog.add_item(item.clone())
                    catalogs.append(catalog)

                for index, variable in enumerate(var_list, start=1):
                    self.logger.info(
                        f"Creating output catalog for item {item.id}, variable: {variable}"
                    )
                    catalog = self.catalog.clone()
                    catalog.id = f"{self.catalog.id}-{item.id}-var-{index}"
                    self._set_item_variable(catalog, item, variable, index)
                    catalogs.append(catalog)

            self.logger.info(
                f"VariableFanOutAdapter.invoke returning {len(catalogs)} catalogs"
            )
            return (self.message, catalogs)
        except Exception:
            # If you get any errors trying process the catalog, just the input
            # message/catalog as a no-op.
            self.logger.exception(
                "Exception during fan out catalog processing: returning input catalog."
            )

        return (self.message, self.catalog)

    def _set_item_variable(
        self, catalog: Catalog, item: Item, variable: str, index: int
    ) -> None:
        """Make a clone of item, amend with a harmony:variable property.

        item is the input catalog's own Item and is reused for every variable, so it
        is cloned rather than modified.
        """
        item_clone = item.clone()
        item_clone.id = f"{item.id}-var-{index}"  # ensures a unique item.
        item_clone.properties["harmony:variable"] = variable
        catalog.remove_links(rel="item")
        catalog.add_item(item_clone)

        self.logger.info(
            f"Set harmony:variable={variable} on item {item_clone.id} in catalog {catalog.id}"
        )
