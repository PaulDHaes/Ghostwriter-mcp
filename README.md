# Ghostwriter-mcp
SpecterOps Ghostwriter MCP server

## Installation
Install the pip packages by going into the directory
```shell
pip install -r requirements.txt
```
If this does not work use a virtual env
```shell
mkdir ghostwriter-python
cd ghostwriter-python
python3 -m venv ghostwriter-env
source ghostwriter-env/bin/activate
cd ..
```
To run this can be done and imported to a mcp server using stdio by simply doing this in the mcp config 
```json
{
  "Ghostwriter-mcp": {
    "command": "/Users/username/Ghostwriter-mcp/ghostwriter-python/ghostwriter-env/bin/python3",
    "args": [
      "/Users/username/Ghostwriter-mcp/main.py"
    ],
    "env": {},
    "working_directory": null
  }
}
```
If your LLM wants to use it over streamable http try using mcpo
```shell
uvx mcpo --port 8000 -- python3 main.py
```
Try connecting to the ip you execute the script from+new port

`http://127.0.0.1:8000`
