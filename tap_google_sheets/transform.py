import math
import json
from datetime import datetime, timedelta
import pytz
import singer
from singer.utils import strftime

LOGGER = singer.get_logger()

# Tranform spreadsheet_metadata: add spreadsheetId, sheetUrl, and columns metadata
def transform_sheet_metadata(spreadsheet_id, sheet, columns):
    # Convert to properties to dict
    sheet_metadata = sheet.get('properties')
    sheet_metadata_tf = json.loads(json.dumps(sheet_metadata))
    sheet_id = sheet_metadata_tf.get('sheetId')
    sheet_url = 'https://docs.google.com/spreadsheets/d/{}/edit#gid={}'.format(
        spreadsheet_id, sheet_id)
    sheet_metadata_tf['spreadsheetId'] = spreadsheet_id
    sheet_metadata_tf['sheetUrl'] = sheet_url
    sheet_metadata_tf['columns'] = columns
    return sheet_metadata_tf

# Tranform spreadsheet_metadata: remove defaultFormat and sheets nodes, format as array
def transform_spreadsheet_metadata(spreadsheet_metadata):
    # Convert to dict
    spreadsheet_metadata_tf = json.loads(json.dumps(spreadsheet_metadata))
    # Remove keys: defaultFormat and sheets (sheets will come in sheet_metadata)
    if spreadsheet_metadata_tf.get('properties'):
        spreadsheet_metadata_tf['properties'].pop('defaultFormat', None)
    spreadsheet_metadata_tf.pop('sheets', None)
    # Add record to an array of 1
    spreadsheet_metadata_arr = []
    spreadsheet_metadata_arr.append(spreadsheet_metadata_tf)
    return spreadsheet_metadata_arr

# Tranform file_metadata: remove nodes from lastModifyingUser, format as array
def transform_file_metadata(file_metadata):
    # Convert to dict
    file_metadata_tf = json.loads(json.dumps(file_metadata))
    # Remove keys
    if file_metadata_tf.get('lastModifyingUser'):
        file_metadata_tf['lastModifyingUser'].pop('photoLink', None)
        file_metadata_tf['lastModifyingUser'].pop('me', None)
        file_metadata_tf['lastModifyingUser'].pop('permissionId', None)
    # Add record to an array of 1
    file_metadata_arr = []
    file_metadata_arr.append(file_metadata_tf)
    return file_metadata_arr

# Convert Excel Date Serial Number (excel_date_sn) to datetime string
# timezone_str: defaults to UTC (which we assume is the timezone for ALL datetimes)
def excel_to_dttm_str(string_value, excel_date_sn, timezone_str=None):
    if not timezone_str:
        timezone_str = 'UTC'
    tzn = pytz.timezone(timezone_str)
    sec_per_day = 86400
    excel_epoch = 25569 # 1970-01-01T00:00:00Z, Lotus Notes Serial Number for Epoch Start Date
    epoch_sec = math.floor((excel_date_sn - excel_epoch) * sec_per_day)
    epoch_dttm = datetime(1970, 1, 1)
    # For out of range values, it will throw OverflowError and it would return the string value
    # as passed in the sheets without any conversion
    try:
        excel_dttm = epoch_dttm + timedelta(seconds=epoch_sec)
    except OverflowError:
        return str(string_value), True
    utc_dttm = tzn.localize(excel_dttm).astimezone(pytz.utc)
    utc_dttm_str = strftime(utc_dttm)
    return utc_dttm_str, False


# transform datetime values in the sheet
def transform_sheet_datetime_data(value, unformatted_value, sheet_title, col_name, col_letter, row_num, col_type):
    if isinstance(unformatted_value, (int, float)):
        # passing both the formatted as well as the unformatted value, so we can use the string value in
        # case of any errors while datetime transform
        datetime_str, _ = excel_to_dttm_str(value, unformatted_value)
        return datetime_str
    else:
        LOGGER.info('WARNING: POSSIBLE DATA TYPE ERROR; SHEET: {}, COL: {}, CELL: {}{}, TYPE: {}'.format(
            sheet_title, col_name, col_letter, row_num, col_type))
        return str(value)

# transform date values in the sheet
def transform_sheet_date_data(value, unformatted_value, sheet_title, col_name, col_letter, row_num, col_type):
    if isinstance(unformatted_value, (int, float)):
        # passing both the formatted as well as the unformatted value, so we can use the string value in
        # case of any errors while date transform
        date_str, is_error =  excel_to_dttm_str(value, unformatted_value)
        return_str = date_str if is_error else date_str[:10]
        return return_str
    else:
        LOGGER.info('WARNING: POSSIBLE DATA TYPE ERROR; SHEET: {}, COL: {}, CELL: {}{}, TYPE: {}'.format(
            sheet_title, col_name, col_letter, row_num, col_type))
        return str(value)

# transform time values in the sheet
def transform_sheet_time_data(value, unformatted_value, sheet_title, col_name, col_letter, row_num, col_type):
    if isinstance(unformatted_value, (int, float)):
        try:
            total_secs = unformatted_value * 86400 # seconds in day
            # Create string formatted like HH:MM:SS
            col_val = str(timedelta(seconds=total_secs))
        except ValueError:
            col_val = str(value)
            LOGGER.info('WARNING: POSSIBLE DATA TYPE ERROR; SHEET: {}, COL: {}, CELL: {}{}, TYPE: {}'.format(
                sheet_title, col_name, col_letter, row_num, col_type))
        return col_val
    else:
        return str(value)

# transform boolean values in the sheet
def transform_sheet_boolean_data(value, unformatted_value, sheet_title, col_name, col_letter, col_type, row):
    if isinstance(value, bool):
        return unformatted_value
    elif isinstance(value, str):
        if value.lower() in ('true', 't', 'yes', 'y'):
            col_val = True
        elif value.lower() in ('false', 'f', 'no', 'n'):
            col_val = False
        # As the float and the int values would be now returned as string itself, we need to check for the special
        # values as a string match rather than the integer/float match
        elif value in ('1', '-1', '1.00', '-1.00'):
            col_val = True
        elif value in ('0', '0.00'):
            col_val = False
        else:
            col_val = str(value)
            LOGGER.info('WARNING: POSSIBLE DATA TYPE ERROR; SHEET: {}, COL: {}, CELL: {}{}, TYPE: {}'.format(
                sheet_title, col_name, col_letter, row, col_type))
        return col_val
    elif isinstance(value, int):
        if value in (1, -1):
            col_val = True
        elif value == 0:
            col_val = False
        else:
            col_val = str(value)
            LOGGER.info('WARNING: POSSIBLE DATA TYPE ERROR; SHEET: {}, COL: {}, CELL: {}{}, TYPE: {}'.format(
                sheet_title, col_name, col_letter, row, col_type))
        return col_val
    elif isinstance(value, float):
        col_val = str(value)
        LOGGER.info('WARNING: POSSIBLE DATA TYPE ERROR; SHEET: {}, COL: {}, CELL: {}{}, TYPE: {}'.format(
            sheet_title, col_name, col_letter, row, col_type))
        return col_val

# transform decimal values in the sheet
def transform_sheet_decimal_data(value, sheet_title, col_name, col_letter, row_num, col_type):
    # Determine float decimal digits
    decimal_digits = str(value)[::-1].find('.')
    if decimal_digits > 15:
        try:
            # ROUND to multipleOf: 1e-15
            col_val = float(round(value, 15))
        except ValueError:
            col_val = str(value)
            LOGGER.info('WARNING: POSSIBLE DATA TYPE ERROR; SHEET: {}, COL: {}, CELL: {}{}, TYPE: {}'.format(
                sheet_title, col_name, col_letter, row_num, col_type))
        return col_val
    else: # decimal_digits <= 15, no rounding
        try:
            col_val = float(value)
        except ValueError:
            col_val = str(value)
            LOGGER.info('WARNING: POSSIBLE DATA TYPE ERROR: SHEET: {}, COL: {}, CELL: {}{}, TYPE: {}'.format(
                sheet_title, col_name, col_letter, row_num, col_type))
        return col_val

# transform number values in the sheet
def transform_sheet_number_data(value, sheet_title, col_name, col_letter, row_num, col_type):
    if type(value) == int:
        return int(value)
    elif type(value) == float:
        return transform_sheet_decimal_data(value, sheet_title, col_name, col_letter, row_num, col_type)
    else:
        LOGGER.info('WARNING: POSSIBLE DATA TYPE ERROR: SHEET: {}, COL: {}, CELL: {}{}, TYPE: {} '.format(
                sheet_title, col_name, col_letter, row_num, col_type))
        return str(value)

# return transformed column the values based on the datatype
def get_column_value(value, unformatted_value, sheet_title, col_name, col_letter, row_num, col_type, row):
        # NULL values
    if value is None or value == '':
        # String columns default to empty string
        if col_type == 'stringValue':
            return ""
        # Number, Boolean, date, time, and datetime columns default to None
        else:
            return None

    # Convert dates/times from Lotus Notes Serial Numbers
    # DATE-TIME
    elif col_type == 'numberType.DATE_TIME':
        return transform_sheet_datetime_data(value, unformatted_value, sheet_title, col_name, col_letter, row_num, col_type)

    # DATE
    elif col_type == 'numberType.DATE':
        return transform_sheet_date_data(value, unformatted_value, sheet_title, col_name, col_letter, row_num, col_type)

    # TIME ONLY (NO DATE)
    elif col_type == 'numberType.TIME':
        return transform_sheet_time_data(value, unformatted_value, sheet_title, col_name, col_letter, row_num, col_type)

    # NUMBER (INTEGER AND FLOAT)
    elif col_type == 'numberType':
        return transform_sheet_number_data(unformatted_value, sheet_title, col_name, col_letter, row_num, col_type)

    # STRING
    elif col_type == 'stringValue':
        return str(value)

    # BOOLEAN
    elif col_type == 'boolValue':
        return transform_sheet_boolean_data(value, unformatted_value, sheet_title, col_name, col_letter, col_type, row)

    # OTHER: Convert everything else to a string
    else:
        LOGGER.info('WARNING: POSSIBLE DATA TYPE ERROR; SHEET: {}, COL: {}, CELL: {}{}, TYPE: {}'.format(
            sheet_title, col_name, col_letter, row, col_type))
        return str(value)

# Transform sheet_data: add spreadsheet_id, sheet_id, and row, convert dates/times
#  Convert from array of values to JSON with column names as keys
def transform_sheet_data(spreadsheet_id, sheet_id, sheet_title, from_row, columns, sheet_data_rows, unformatted_rows):
    sheet_data_tf = []
    row_num = from_row
    # Create sorted list of columns based on columnIndex
    cols = sorted(columns, key=lambda i: i['columnIndex'])

    for (row, unformatted_row) in zip(sheet_data_rows, unformatted_rows):
        # If empty row, SKIP
        if row == []:
            LOGGER.info('EMPTY ROW: {}, SKIPPING'.format(row_num))
        else:
            sheet_data_row_tf = {}
            # Add spreadsheet_id, sheet_id, and row
            sheet_data_row_tf['__sdc_spreadsheet_id'] = spreadsheet_id
            sheet_data_row_tf['__sdc_sheet_id'] = sheet_id
            sheet_data_row_tf['__sdc_row'] = row_num
            col_num = 1
            padded_row = row + [None] * (len(cols) - len(row))
            padded_unformatted_row = unformatted_row + [None] * (len(cols) - len(unformatted_row))

            for (value, unformatted_value) in zip(padded_row, padded_unformatted_row):
                # Select column metadata based on column index
                col = cols[col_num - 1]
                col_skipped = col.get('columnSkipped')
                if not col_skipped:
                    # Get column metadata
                    col_name = col.get('columnName')
                    col_type = col.get('columnType')
                    col_letter = col.get('columnLetter')

                    # get column value based on the type of the value
                    col_val = get_column_value(value, unformatted_value, sheet_title, col_name, col_letter, row_num, col_type, row)

                    sheet_data_row_tf[col_name] = col_val
                col_num = col_num + 1
            # APPEND non-empty row
            sheet_data_tf.append(sheet_data_row_tf)
        row_num = row_num + 1
    return sheet_data_tf, row_num
