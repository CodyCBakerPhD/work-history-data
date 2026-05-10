# Work history data

A raw API dump from GitHub about all my activity.
To be used in GitHub project dashboards.



### Batch download (Python API)

```python
import gzip
import json
import requests

url = "https://raw.githubusercontent.com/CodyCBakerPhD/work-history-data/refs/heads/min/derivatives/all_info.min.json.gz"
response = requests.get(url)
all_info = json.loads(gzip.decompress(data=response.content))
```
