PID=$$
# L=$(uname -n)
if ! [ -z "$1" ]; then files="\"ifile\": \"$1\""; else exit 1; fi
echo -e "[\"A\", [\"nwchem\", {$files }, {}, $PID]]" >/dev/udp/127.0.0.1/50000
exec sleep 10