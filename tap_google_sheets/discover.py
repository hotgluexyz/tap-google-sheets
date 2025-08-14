from singer.catalog import Catalog, CatalogEntry, Schema
from tap_google_sheets.schema import STREAMS


def discover(client,spreadsheet_ids):
    catalog = Catalog([])
    discovered_metadata_streams = []
    for spreadsheet_id in spreadsheet_ids:
        for stream, stream_obj in STREAMS.items():
            stream_object = stream_obj(client, spreadsheet_id.get("id"))
            schemas, field_metadata = stream_object.get_schemas()
            metadata_stream_list = ["file_metadata","spreadsheet_metadata","sheet_metadata","sheets_loaded"]
            # loop over the schema and prepare catalog
            for stream_name, schema_dict in schemas.items():
                if stream_name not in metadata_stream_list:
                   standard_name = ''.join(x for x in spreadsheet_id.get('name').title() if not x.isspace())
                   stream_name_new = f"{standard_name}_{stream_name}"
                   field_metadata[stream_name_new]=  field_metadata[stream_name]
                   stream_name = stream_name_new

                schema = Schema.from_dict(schema_dict)
                mdata = field_metadata[stream_name]

                # get the primary keys for the stream
                #   if the stream is from STREAM, then get the key_properties
                #   else use the "table-key-properties" from the metadata
                if not STREAMS.get(stream_name):
                    key_props = None
                    # get primary key for the stream
                    for mdt in mdata:
                        table_key_properties = mdt.get('metadata', {}).get('table-key-properties')
                        if table_key_properties:
                            key_props = table_key_properties
                else:
                    stream_obj = STREAMS.get(stream_name)(client, spreadsheet_id)
                    key_props = stream_obj.key_properties

                if stream_name in discovered_metadata_streams:
                    continue
                elif stream_name in metadata_stream_list:
                    discovered_metadata_streams.append(stream_name)

                catalog.streams.append(CatalogEntry(
                    stream=stream_name,
                    tap_stream_id=stream_name,
                    key_properties=key_props,
                    schema=schema,
                    metadata=mdata
                ))

    return catalog
