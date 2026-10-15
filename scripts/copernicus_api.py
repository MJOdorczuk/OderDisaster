
import requests

token_url = (
    "https://identity.dataspace.copernicus.eu/"
    "auth/realms/CDSE/protocol/openid-connect/token"
)
catalogue_url = (
    "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
)
download_base_url = (
    "https://download.dataspace.copernicus.eu/odata/v1/Products"
)

BEGINHOUR = "T00:00:00.000Z"
END_HOUR = "T23:59:59.999Z"

def get_access_token():
    """Request an OAuth access token from Copernicus Data Space."""

    # Use credentials stored in local files
    # Code smell? Should those be passed as arguments?
    with open("./local/id", "r") as f:
        id = f.read().strip()
    with open("./local/secret", "r") as f:
        secret = f.read().strip()

    response = requests.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": id,
            "client_secret": secret
        },
        timeout=60
    )

    response.raise_for_status()

    return response.json()["access_token"]

def search_tile(tile, token, date):
    """
    Search for Sentinel-2 Level-2A products for one MGRS tile
    during the requested date range.
    """

    filter_expression = (
        "Collection/Name eq 'SENTINEL-2' "
        f"and ContentDate/Start ge {date + BEGINHOUR} "
        f"and ContentDate/Start lt {date + END_HOUR} "
        f"and contains(Name, '_{tile}_') "
        "and Attributes/OData.CSC.StringAttribute/any("
        "att:att/Name eq 'productType' "
        "and att/OData.CSC.StringAttribute/Value eq 'S2MSI2A'"
        ")"
    )

    headers = {
        "Authorization": f"Bearer {token}"
    }

    params = {
        "$filter": filter_expression,
        "$orderby": "ContentDate/Start asc",
        "$top": 100
    }

    response = requests.get(
        catalogue_url,
        headers=headers,
        params=params,
        timeout=60
    )

    response.raise_for_status()

    return response.json()["value"]

def download_product(product, token, download_dir):
    """
    Download one Sentinel product as a ZIP archive.
    Skips it if the ZIP already exists.
    """

    product_id = product["Id"]
    product_name = product["Name"]

    output_zip = download_dir / f"{product_name}.zip"

    if output_zip.exists():
        print(f"Already downloaded — skipped:\n  {output_zip.name}")
        return

    download_url = f"{download_base_url}({product_id})/$value"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    print(f"\nDownloading:\n  {product_name}")

    with requests.get(
        download_url,
        headers=headers,
        stream=True,
        timeout=600
    ) as response:

        response.raise_for_status()

        with open(output_zip, "wb") as file:

            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    file.write(chunk)

    print(f"Saved:\n  {output_zip}")