#!/usr/bin/python 

import urllib.request                                   # To support inteeraction with web
import urllib.parse                                     # To prepare POST data
from http import cookiejar                              # To support auto handling cookies

import os
import mimetypes                                        # For the multipart POSTing


try:
    import lxml.html                                    # To parse html responces
except ImportError:                                     # So, the nessesary library may be not exists
    print("Для правильной работы необходима библиотека lxml")
    quit(1)



jar = cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(jar)
    )                                                   # Some magic to support cookies

server = "https://mail.yandex.ru"                       # Just a server url
#========================================
# Multipart POST encoder begins here
#========================================
def encode_multipart_formdata(fields, files=False):
    """
    fields is a sequence of (name, value) elements for regular form fields.
    files is a sequence of (name, filename, value) elements for data to be uploaded as files
    Return (content_type, body) ready for httplib.HTTP instance
    """
    BOUNDARY = '----------ThIs_Is_tHe_bouNdaRY_$'.encode('utf-8')
    CRLF = '\r\n'.encode('utf-8')
    L = []
    for (key, value) in fields:
        L.append('--'.encode('utf-8') + BOUNDARY)
        L.append('Content-Disposition: form-data; name="'.encode('utf-8')+key.encode('utf-8')+'"'.encode('utf-8'))
        L.append(''.encode('utf-8'))
        L.append(value.encode('utf-8'))
    if files:
        for (key, filename, value) in files:
            L.append('--'.encode('utf-8') + BOUNDARY)
            L.append('Content-Disposition: form-data; name="'.encode('utf-8')+key.encode('utf-8')+'"; filename="'.encode('utf-8')+filename.encode('utf-8')+'"'.encode('utf-8'))
            L.append('Content-Type: '.encode('utf-8')+get_content_type(filename).encode('utf-8'))
            L.append(''.encode('utf-8'))
            L.append(value)
    L.append('--'.encode('utf-8') + BOUNDARY + '--'.encode('utf-8'))
    L.append(''.encode('utf-8'))
    body = CRLF.join(L)
    content_type = 'multipart/form-data; boundary='.encode('utf-8')+BOUNDARY
    return content_type.decode('utf-8'), body

def get_content_type(filename):
    return mimetypes.guess_type(filename)[0] or 'application/octet-stream'
#========================================
# Multipart POST encoder ends here
#========================================



class Message:#Just a message
    id = ""
    href = ""
    sender = ""
    reserver = ""
    subject = ""
    text = ""
    files = []                                                  # For local ones. Contains [Filepath] array
    attachments = []                                            # For attachments on server. Contains [(Filename, link)] array
    new = False
                                                                #========================================
    def __init__(self, _id="0", _href="", _new=False):          #Class constructor
        self.id = _id                                           #========================================
        self.href = _href
        if _new:
            self.new = _new
                                                                #========================================
    def get(self):                                              # Get full message from server
        if self.href == "":                                     #========================================
            return 1
        responce = opener.open(
            server+self.href
            ).read().decode('utf-8')
        page = lxml.html.fromstring(responce)                   #Parse response html page
        msg_subj = page.find_class(
            "b-message-head__subject-text"
            )                                                   # Extract subject
        self.subject = msg_subj[0].text_content()
        msg_head = page.find_class(
            "b-message-head__email"
            )                                                   # Extract reserver and sender
        self.reserver = msg_head[0].text_content()
        self.sender = msg_head[1].text_content()
        msg_attach = page.find_class(
            "b-message-attach__actions-link"
            )                                                   # Extract attachments information
        msg_attach_names = page.find_class(
            "b-message-attach__info"
            )
        msg_attach_tree = page.find_class(
            "b-message-attach__i js-attachment"
            )
        #b-message-attach__info
        #b-message-attach__i js-attachment
        for attach,attach_name,attach_tree in zip(msg_attach,msg_attach_names,msg_attach_tree):
            self.attachments.append([
                attach_name.text_content(),
                attach.get("href")
                ])
            attach_tree.drop_tree()                             # Remove attachments information from message text
        msg_body = page.find_class("b-message-body__content")
        self.text = msg_body[0].text_content()                  # Extract message text
        return self
                                                                #========================================
    def send(self):                                             # Sends a message
        response = opener.open(                                 #========================================
            server+"/lite/compose"
            ).read().decode('utf-8')
        page = lxml.html.fromstring(response)
        page.forms[0].fields['subj'] = self.subject
        page.forms[0].fields['send'] = self.text
        page.forms[0].fields['to'] = self.reserver              # Set up nessesary fields
        form_summary = page.forms[0].form_values()
        form_summary.append(['doit','Отправить'])               # Some magic to emulate button click

        if self.files:                                          # Prepare files to attach if exist
            files = []                                          # Format for files
            for fpath in self.files:                            # [('att', filename, filedata)]
                fdata = open(fpath, 'rb').read()
                files.append(
                    ['att',os.path.basename(fpath),fdata]
                    )
                
        ct, body = encode_multipart_formdata(                   # Encode message to multipost form.  
                    form_summary,
                    files
                    )
        head = {"Content-type": ct}                             # Tell to server what kind of form we sending
        request = urllib.request.Request(                       # Prepare request with form
            server+page.forms[0].action, 
            body, 
            head)
        response = opener.open(request).read().decode('utf-8')  # Send multipost form to server
        return
                                                                #========================================
    def save_attach(self,path,index=False,name=False):          # Saves remote attachments to hard disk
                                                                #========================================
        savelist = []                                           # List of attachments that will be saved
        if index:
            try:
                savelist.append(self.attachments[index])
            except IndexError:
                return 1                                        # If index of attach is defined - add attachment link to savelist
            iterator = ""                                       # for 1 attachment iterator isn't needed
            step = ""
        else:
            savelist = self.attachments                         # If index is undefined - add all attachments
            iterator = 0                                        # Start iterator from 0 (for name overwriting)
            step = 1
        
        for fname,flink in savelist:
            if name:                                            # If name overwriting is on, rename saved files. 
                fname = name+str(iterator)                      # Iterator needed to prevent overwriting saved attachments with same name
            fstream = open(path+'/'+fname, 'wb')                # Open target file for writing
            response = opener.open(server+flink).read()         # Get attach from server
            fstream.write(response)                             # Write attach to file
            fstream.close()
            self.files.append(path+'/'+fname)                   # Add path to Message.files
            iterator += step
        return
    
    def mark(self,unread=False):
        if self.href == "":                                     #========================================
            return 1
        response = opener.open(                                 #========================================
            server+self.href
            ).read().decode('utf-8')
        page = lxml.html.fromstring(response)
        f = page.forms[0].form_values()
        if unread:
            f.append([ 'unmark','Не прочитано'])
        else:
            f.append(['mark', 'Прочитано'])
        post = urllib.parse.urlencode(
            f
            ).encode('utf-8')
        opener.open(server+page.forms[0].action,post)
    
    def delete(self):
        if self.href == "":                                     #========================================
            return 1
        response = opener.open(                                 #========================================
            server+self.href
            ).read().decode('utf-8')
        page = lxml.html.fromstring(response)
        f = page.forms[0].form_values()
        f.append([ 'delete','Удалить'])
        post = urllib.parse.urlencode(
            f
            ).encode('utf-8')
        opener.open(server+page.forms[0].action,post)
        self.id = ""
        self.href = ""
        self.attachments = []                                           
        self.new = False
        
        
                                                                #========================================
def auth(l,p):                                                  # Authorization request
    post = urllib.parse.urlencode({                             #========================================
        "login":l,
        "passwd":p,
        "submit":"commit",
        "mode":"auth"
        }).encode('utf-8')                                      # Post data to send, encoded to utf-8
    opener.open("https://passport.yandex.ru/passport",post)

                                                                #========================================
def getinbox(unread=False):                                                 # Gets inbox mails list
    msglist = {}                                                #========================================
    #=======================
    #TODO Messages from all pages
    #=======================
    if unread:
        inbox = "/lite/unread"
    else:
        inbox = "/lite/inbox"
            
    responce = opener.open(
        server+inbox
        ).read().decode('utf-8')# Get a page with messages list
    page = lxml.html.fromstring(responce) # parse it!
    message_links = page.find_class(
        "b-messages__message__left"
        )                                                       # Select messages href's
    for link in message_links:
        # Write it in message list { id : Message}
        # Where message contains a values of some fields like a text, subject, href, etc...
        # On this step we are just writing ids and hrefs. Other fields will be obtained by getmessage(message)
        href_parsed = link.get("href").split(sep="/")
        href = "/lite/message/"+href_parsed[3]
        id = href_parsed[3]                                     # Select id from /lite/message/[id]
        try:
            if href_parsed[4] == "new":                         # If link like /lite/message/[id]/new - set Message.new as True
                new = True
        except IndexError:
            new = False
        msglist[id] = Message(id,href,new)
    return msglist

#========================================
# Testing, testing, testing....
#========================================
# https://mail.yandex.ru/neo2/#message/2300000003086117952
                                                                
#auth("laboratory.306b","qwantarik")

#msg_list = getinbox()

#msg_list["2300000003092448947"].get()
#print("Sender: "+msg_list["2300000003092448947"].sender)
#print("Subject: "+msg_list["2300000003092448947"].subject)
#print("Text: "+msg_list["2300000003092448947"].text)
#msg_list["2300000003092448947"].save_attach('/home/xomachine',name="script.sh")
#msg_list["2300000003092448947"].delete()
