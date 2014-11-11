# -*- coding: utf-8 -*-
'''
    This file is part of O4erednik.

    O4erednik is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License or
    (at your option) any later version.

    O4erednik is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with O4erednik.  If not, see <http://www.gnu.org/licenses/>.

    Copyright 2014 Fomichev Dmitriy
'''

from http.server import HTTPServer, BaseHTTPRequestHandler

class HTTPHandler(BaseHTTPRequestHandler):

    
    
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        
        
        
        # print(self.wfile)
        self.wfile.write("""
<html>
<head>
<title>The Queue status.</title>
<style type=\"text/css\">
h1{
font-size: 150%;
font-family: Verdana, Arial, Helvetica, sans-serif;
color: #333366;
}
h2{
font-size: 120%;
font-family: Verdana, Arial, Helvetica, sans-serif;
color: #666666;
}</style></head>""".encode('utf-8'))
        
        queue, now, recent = self.getinfo()
        if ((len(queue) != 0)or(len(now)!=0)):
            
            self.wfile.write(("<body><h1>Status of the computer: busy...</h1>").encode('utf-8'))
            self.wfile.write(("<h2>Now running:</h2><table border=\"1\" cellpadding=\"7\">").encode('utf-8'))
            # If someone went to "http://something.somewhere.net/foo/bar/",
            # then s.path equals "/foo/bar/".
            self.wfile.write(("<tr><td>Machine</td><td>File</td></tr>").encode('utf-8'))
            for name, target in now.values():
                if target is None:
                    target = "this"
                self.wfile.write(("<tr><td>"+target+"</td><td>"+name+"</td></tr>").encode('utf-8'))
            
            self.wfile.write(("</table><h2>In queue:</h2><table border=\"1\" cellpadding=\"7\">").encode('utf-8'))
            # If someone went to "http://something.somewhere.net/foo/bar/",
            # then s.path equals "/foo/bar/".
            self.wfile.write(("<tr><td>N</td><td>File</td></tr>").encode('utf-8'))
            it = 1
            for name in queue.values():
                self.wfile.write(("<tr><td>"+str(it)+"</td><td>"+name+"</td></tr>").encode('utf-8'))
                it += 1
            self.wfile.write(("</table>").encode('utf-8'))
        else: 
            self.wfile.write(("<body><h1>Status of the computer: free!</h1>").encode('utf-8'))
        self.wfile.write(("<h2>Recent:</h2><table border=\"1\" cellpadding=\"7\">").encode('utf-8'))
        # If someone went to "http://something.somewhere.net/foo/bar/",
        # then s.path equals "/foo/bar/".
        self.wfile.write(("<tr><td>N</td><td>File</td></tr>").encode('utf-8'))
        it = 1
        for name in recent:
            self.wfile.write(("<tr><td>"+str(it)+"</td><td>"+name+"</td></tr>").encode('utf-8'))
            it += 1
        self.wfile.write("</table></body></html>".encode('utf-8'))
        #self.wfile.close()


class Backend():

    def __init__(self, shared):
        super(Backend, self).__init__()
        self.shared = shared
        self.recent = list()
        self.sendto = lambda x: shared.udpsocket.sendto(
            x.encode('utf-8'),
            ('127.0.0.1', 50000)
            )
        self.sEmpty(0,0)
        self.signals = {
            'add': self.sAdd,
            'empty': self.sEmpty,
            'start': self.sStart,
            'error': self.sDone,
            'done': self.sDone,
            }
        self.handler = HTTPHandler
        self.handler.getinfo = lambda x : (self.qnames, self.runningnow, self.recent)
        

    def run(self, server_class=HTTPServer):
        server_address = ('', 8000)
        httpd = server_class(server_address, self.handler)
        httpd.serve_forever()
        


    def signal(self, *signal):
        if signal[0] in self.signals:
            self.signals[signal[0]](*signal)

# Signals


    def sEmpty(self, func, job=None):
        self.qnames = dict()
        self.runningnow = dict()

    def sAdd(self, func, job):
        self.qnames[job.id] = job.files['ifile']
        

    def sDone(self, func, uid):
        if type(uid) is int:
            realuid = uid
        else:
            realuid = int(uid)
        popped = self.qnames.pop(uid, "None")
        if popped == "None":
            popped = self.runningnow.pop(uid, "None")
        if popped != "None":
            self.recent.append(popped)
        if len(self.recent) > 5:
            self.recent.pop()

    def sStart(self, func, job, target=None):
        self.qnames.pop(job.id, "None")
        self.runningnow[job.id] = (job.files['ifile'], target)

            