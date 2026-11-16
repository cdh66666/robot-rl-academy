"""Loopback static handler supporting single-byte ranges for video seeking."""
from __future__ import annotations

import http.server
import os
import re


class RangeRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def send_head(self):
        self._range_remaining = None
        range_header = self.headers.get("Range")
        path = self.translate_path(self.path)
        if not range_header or not os.path.isfile(path):
            return super().send_head()
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
        if not match or not any(match.groups()):
            return super().send_head()
        stat = os.stat(path)
        # When an If-Range validator does not match, send the full current file.
        if_range = self.headers.get("If-Range")
        if if_range and if_range != self.date_time_string(stat.st_mtime):
            return super().send_head()
        size = stat.st_size
        first, last = match.groups()
        if not first:
            suffix = int(last)
            start, end = max(0, size-suffix), size-1
        else:
            start, end = int(first), min(int(last) if last else size-1, size-1)
        if size == 0 or start >= size or start > end:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        file = open(path, "rb")
        file.seek(start)
        self._range_remaining = end-start+1
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(self._range_remaining))
        self.send_header("Last-Modified", self.date_time_string(stat.st_mtime))
        self.end_headers()
        return file

    def copyfile(self, source, outputfile):
        if self._range_remaining is None:
            return super().copyfile(source, outputfile)
        remaining = self._range_remaining
        while remaining:
            chunk = source.read(min(64 * 1024, remaining))
            if not chunk: break
            outputfile.write(chunk)
            remaining -= len(chunk)
