# Service to fan out all variables in a file
import os
from tempfile import TemporaryDirectory

import xarray as xr
from harmony_service_lib import BaseHarmonyAdapter
from harmony_service_lib.message import Message
from harmony_service_lib.util import download
from net2cog.netcdf_convert import get_all_data_variables
from pystac import Catalog, Item


class VariableFanOutAdapter(BaseHarmonyAdapter):
    """
    See See https://github.com/nasa/harmony-service-lib-py
    for documentation and examples.
    """

    def invoke(self) -> tuple[Message, Catalog | list[Catalog]]:
        """Writes a catalog per (item, variable).

        The harmony variable fan out service processes the incoming
        ``Harmony.message``.  For each Item it finds the Item's source in the
        message.  If that source explicitly requests variables, those are the
        Item's variables and nothing is downloaded.

        If the source has not explicitly asked for variables from the file,
        this routine downloads the Item's data asset and generates its list of
        variables using net2cogs get_all_data_variables routine directly.
        [Generally (always?) there will be one Item per Catalog.]

        For every item and every variable it writes a catalog containing the
        variable's name added to the item's properties as ``harmony:variable``.

        An Item whose data file returns no variables gets a catalog holding
        just a clone of the item, so the downstream service sees the item and
        fails (net2cog will also find no variables in the file).

        Harmony will then call the downstream service, net2cog, with each of
        the catalogs in parallel fanning out to num-of-variables pods per item.

        Any errors raised are caught, logged, and then the original input
        message and catalog are returned to Harmony.

        If the environment variable ``HARMONY_VARIABLE_FAN_OUT_ENABLED`` is ``false``
        the input message and catalog are returned unchanged.  Harmony's
        local Harmony-In-A-Box defaults to ``false`` so the fan out is
        skipped locally without fanning out and repeating downloads.

        Returns a tuple of the input Message and either the input Catalog (on
        error), or a list of catalogs, one per
        item/variable pair, each containing a single item from the input
        catalog amended with one of its variables.

        """
        if not self.catalog:
            raise RuntimeError(
                "The harmony variable fan out service requires an input STAC catalog."
            )

        if (
            os.environ.get("HARMONY_VARIABLE_FAN_OUT_ENABLED", "true").lower()
            == "false"
        ):
            self.logger.info(
                "HARMONY_VARIABLE_FAN_OUT_ENABLED is false; exiting without creating fan out catalogs"
            )
            return (self.message, self.catalog)

        try:
            # Clone a catalog for every variable of every Item. Requested
            # variables are used as-is; otherwise each Item's own variables are
            # discovered via href download.
            catalogs = []
            for item in self.catalog.get_items():
                source = self._get_item_source(item)
                if source.variables:
                    var_list = [var.name for var in source.variables]
                    self.logger.info(
                        f"Using requested variables for item {item.id}: {var_list}"
                    )
                else:
                    var_list = self._discover_variables(item)

                # If we don't discover any variables with _discover_variables,
                # we add this Item alone to a catalog, for the unlikely case of
                # multiple items, we don't want to just pass on the original
                # catalog in case we can still process the second item. (rather
                # than just returning the input catalog)
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

    def _discover_variables(self, item: Item) -> list[str]:
        """Download item's data asset and return the variables net2cog can process."""
        asset = next(v for v in item.assets.values() if "data" in (v.roles or []))
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
                # use net2cogs function directly to get a list of
                # variables that can be processed by net2cog. which is
                # described as A list of paths to all variables in the
                # `data_vars` property of any node in the
                # DataTree. These variables are filtered to remove any
                # variables that are 1-D, attribute-only (e.g., CRS
                # definitions), dtype = string(S1/S2), or variable without dimensions.
                return get_all_data_variables(input_datatree, self.logger)

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
