# Work history data

A raw API dump from GitHub about all my activity.
To be used in GitHub project dashboards.



### Batch download (Python API)

```python
import gzip
import json
import urllib.request

url = "https://raw.githubusercontent.com/CodyCBakerPhD/work-history-data/refs/heads/min/data.min.json.gz"
with urllib.request.urlopen(url) as response:
    data = json.loads(gzip.decompress(response.read()))
```
