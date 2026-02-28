# My work history

A raw API dump from GitHub about all my activity. To be used to create a dashboard automatically.



### Run from CLI

```text
pip install -e .

mywork update --directory ./derivatives --recency [number of days] --username [GitHub username]
```



### Batch download (Python API)

```python
import gzip
import json
import requests

url = "https://raw.githubusercontent.com/CodyCBakerPhD/work-history-data/refs/heads/min/derivatives/all_info.min.json.gz"
response = requests.get(url)
all_info = json.loads(gzip.decompress(data=response.content))
```
