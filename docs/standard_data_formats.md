# Standard Data Format Specifications for DWRi's Data Scraping System

DWRi retrieves time series of flow and other measurements from multiple different data providers. To accomplish this, DWRi maintains a data scraping system that manages automated jobs that retrieve data and load them into DWRi's database. Historically, data have been scraped from different sources in whatever format in which they were provided. This approach provides flexibility to data providers, but incurs the overhead for DWRi of having to adapt to many different data formats along with inevitable errors that occur when sources change their formats for whatever reason.

Standardizing the acceptable data formats to be used by data providers is a way for DWRi to reduce the amount of time and effort required to build and maintain scripts that scrape data from different sources along with reducing errors in interpreting data when loading them into DWRi's database. This document describes DWRi's preferred and approved data formats for use by partners who provide data to DWRi. 

There are two acceptable formats - comma separated values (CSV) and JavaScript Object Notation (JSON) that are described in the sections below. Both of these formats are designed for simple encoding of time series of observational data along with associated metadata that will aid in their interpretation.

As an alternative to these data formats, data providers may also serve their data through a public OGC SensorThings API (version 1.1) with the Data Array extension enabled. The SensorThings API is a standard for managing and sharing sensor data, offering a RESTful interface to access time series data from Information of Things (IoT) devices. For more information, refer to the [SensorThings API v1.1 specification](https://docs.ogc.org/is/18-088/18-088.html).

## Definitions

The following are useful definitions in the specification of the acceptable data formats:

* **Monitoring site**: a location at which observations are made.
* **Sensor**: A sensing device used to collect observations.
* **ObservedProperty**: The variable that is measured (e.g., water level, flow, storage volume)
* **Datastream**: is a time series of numeric observations of a particular observed variable  collected at a single monitoring site/location, using a consistent sensor or observation procedure.
* **ProcessingLevel**: The degree of processing or quality control that has been applied to observations (e.g., raw data versus quality controlle data).
* **Units**: The measurment units associated with an observation (e.g., cubic feet per second, acre-feet, feet).

## Design Principles

The data formats described below were designed according to the following principles:

* The data formats should enable encoding of both data and descriptive metadata 
* The data formats should be simple to create
* The data formats should be simple to retrieve and parse

## Handling Datetime Values

It is necessary that datatime values representing timestamps for collected data be represented accurately in data files supplied to DWRi to avoid any ambiguity in when a data value was recorded. For both of DWRi's accepted data formats (CSV and JSON), all timestamps MUST be specified as a single string value encoded using the [ISO 8601 format](https://en.wikipedia.org/wiki/ISO_8601). This international standard for formatting datatime values provides some flexibility; however, we define here the exact format that MUST be used in all provided data as follows:

“YYYY-MM-DDThh:mm:ss.sTZD” 

Where:

* YYYY = four-digit year
* MM   = two-digit month (01=January, etc.)
* DD   = two-digit day of month (01 through 31)
* T    = character that appears literally in the string to indicate the beginning of the time element
* hh   = two digits of hour (00 through 23) (am/pm NOT allowed)
* mm   = two digits of minute (00 through 59)
* ss   = two digits of second (00 through 59)
* s    = one or more digits representing a decimal fraction of a second (only where needed and can be omitted)
* TZD  = time zone designator ("Z" representing UTC time or "+hh:mm" or "-hh:mm" representing some offset from UTC time)

Examples:

The following are all examples of how to encode the datetime instant of December 6, 2024 at 8:15:30 AM, U.S. Mountain Standard Time.

### Encoding using UTC Time:

"2024-12-06T15:15:30Z" OR "2024-12-06T15:15:30+00:00"

where the "Z" or "+00:00" part of the date encoding indicates a zero offset from UTC time.

### Encoding using U.S. Mountain Standard Time:

"2024-12-06T08:15:30-07:00"

Any of the above ISO 8601 compliant encodings are acceptable for the exact same time instant. 

## CSV Data Format Specification

The comma separated values (CSV) format is a simple ASCII text file where data are written in a tabular format with a comma used as the delimiter between columns and each row representing a single datetime instant. 

The following are the requirements for the CSV file format:

1. Data MUST be organized in a "wide" tabular format with a single column containing the timestamp for each row and where each column represents a time series of data values for a Datastream.
2. A comma character MUST be used as the delimiter between columns of data.
3. Each CSV file MUST have a single column as the first column in the table with the column name "timestamp" that contains the timestamp of the observed data values. Each subsequent column after the Timestamp column MUST contain a time series of observed data.
4. Datetime values in the timestamp column MUST be specified in the ISO 8601 datetime format.
5. Timestamps for data MUST either be supplied using UTC time or MUST specify the offset from UTC time as part of the timestamp value to avoid ambiguity in specification of time offsets and daylight saving time.
6. Each CSV file MUST contain at least one column of data values but can represent additional time series of data in subsequent columns, with data values for each time series contained in a separate column. 
7. Files may have a descriptive header with metadata about the contents of the file. Each row in the descriptive header MUST be prefixed with a hash symbol and a space - "# ". 
8. Each CSV file MUST have a single row that follows any descriptive header and that contains names for each column in the file. It is recommended that column names are defined and described in the descriptive header at the top of the file. The row with column names should not be prefixed with "# ".
9. Each file MUST use either a single numeric value to represent missing data points (e.g., -9999 is recommended) or must use a single string value (e.g., "NaN"). This NoData value should be defined in the descriptive header for the file. All non-numeric values included in numeric data value columns will be converted to -9999 upon loading into DWRi's database.
10. Column names used in the header row of the CSV file MUST be unique and MUST consist of alphanumeric characters using a through z, 0 through 9, dashes, or underscores.  

The following is an example showing the CSV file format where timestamps are specified in UTC time. The ". . ." characters indicate that any number of descriptive header rows may be included and any number of data rows may be included:

```
# Descriptive header row 1
# . . .
# Descriptive header row n
timestamp,waterlevel_ft,discharge_cfs
2023-10-26T08:00:00Z,20.5,35.0
2023-10-26T08:15:00Z,21.2,33.1
2023-10-26T08:30:00Z,21.8,37.2
. . .
```

The following is an example showing the CSV file format where timestamps are specified in U.S. Mountain Standard Time:

```
# Descriptive header row 1
# . . .
# Descriptive header row n
timestamp,waterlevel_ft,discharge_cfs
2023-10-26T01:00:00-07:00,20.5,35.0
2023-10-26T01:15:00-07:00,21.2,33.1
2023-10-26T01:30:00-07:00,21.8,37.2
. . .
```

The following are optional features and best practices for the CSV file format:

1. Multiple time series of data with mismatched timestamps should be placed in separate CSV files to avoid sparsely populated columns and gaps in the data contained within a single file.
2. Descriptive header information included in the file should include:
    * Date/time at which the file was generated
    * Information about the organization providing the data and responsible individual(s) with contact information
    * Information about the site/location at which the data were collected including name and coordinates
    * Definitions of the column headers in the files, including:
        * Observed property/parameter
        * Units of measure
        * Methods used for data collection
        * Processing level or quality control information
    * Any discliamers for the data 

## JSON Data Format Specification

As an alternative to CSV, some organizations may want to provide access to their data via a web service application programming interface using a standardized data encoding using JSON. The JSON encoding format is flexible in that any metadata can be encoded within the JSON payload, but the structure of the actual data values and timestamp information is fixed.

The following are the requirements for the JSON data format:

1. The JSON payload must contain a key/value pair with a key called "data_array" whose value is a JSON array that contains the timestamps and data values for Datastreams contained within the payload.
2. The JSON payload must contain a key/value pair containing timestamp information for data values with the key called "timestamp". 
3. Datetime values in the timestamp key/value pair MUST be specified in the ISO 8601 datetime format.
4. Timestamps for data MUST either be supplied using UTC time or MUST specify the offset from UTC time as part of the timestamp value to avoid ambiguity in specification of time offsets and daylight saving time.
3. Each observed property (measured variable) should have a unique name (the equivalent of column names in a CSV file) used as the key to identify it within the data_array, with a value specified for each observed property at each timestamp. 
6. Each JSON payload MUST contain data values for at least one Datastream but can represent additional time series of data, with data values for each separate Datastream specified as the values for a key/value pair having a unique name for that Datastream (e.g., keys as "waterlevel_ft" or "discharge_cfs" with numeric vales for those observed properties). 
7. JSON payloads may contain descriptive metadata about the contents of the payload as separate key/value pairs. This descriptive metadata should be specified outside of the "data_array" key/value pair. 
9. Each JSON payload MUST use either a single numeric value to represent missing data points (e.g., -9999 is recommended) or must use a single string value (e.g., "NaN"). This NoData value should be defined in the descriptive header/metadata within the file. All non-numeric values included in numeric data key/value pairs will be converted to -9999 upon loading into DWRi's database.
10. Names used as the keys in key/value pairs for observed properties should consist of alphanumeric characters using a through z, 0 through 9, dashes, or underscores.

The following is an example of the minimum JSON structure required to encode the same data shown for the CSV examples above.

```JSON
{
  "data_array": [
      {
        "timestamp": "2023-10-26T08:00:00Z",
        "waterlevel_ft": 20.5,
        "discharge_cfs": 35
      },
      {
        "timestamp": "2023-10-26T08:15:00Z",
        "waterlevel_ft": 21.2,
        "discharge_cfs": 33.1
      },
      {
        "timestamp": "2023-10-26T08:30:00Z",
        "waterlevel_ft": 21.8,
        "discharge_cfs": 37.2
      }
  ]
}
```

Where a data provider wishes to include descriptive metadata in the JSON payload, this can be done by adding additional key/value pairs and/or JSON metadata objects outside of the data_array key/value pair. For example, the following JSON payload includes information about when the query was run that generated the JSON as well as information about the station from which the data was extracted along with additional information about each Datastream included in the JSON payload. There are no restrictions to what metadata can be included in the JSON file provided the following:

1. There is only one ```data_array``` element containing data within the JSON payload.
2. All of the metadata contained in the JSON payload appears outside of the ```data_array``` element.

```JSON
{
  "query_date": "2023-10-26T09:00:00Z",
  "station_name": "Logan River station xyz",
  "latitude": 41.7397,
  "longitude": -111.7915,
  "datastreams": [
    {
      "name": "Water level",
      "code": "waterlevel_ft",
      "units": "feet",
      "processing_level_code": "0",
      "processing_level_description": "Raw data"
    },
    {
      "name": "Discharge",
      "code": "discharge_cfs",
      "units": "Cubic feet per second",
      "processing_level_code": "0",
      "processing_level_description": "Raw data"
    }
  ],
  "data_arrary": [
    {
      "timestamp": "2023-10-26T08:00:00Z",
      "waterlevel_ft": 20.5,
      "discharge_cfs": 35.0
    },
    {
      "timestamp": "2023-10-26T08:15:00Z",
      "waterlevel_ft": 21.2,
      "discharge_cfs": 33.1
    },
    {
      "timestamp": "2023-10-26T08:30:00Z",
      "waterlevel_ft": 21.8,
      "discharge_cfs": 37.2
    }
  ]
}
```
