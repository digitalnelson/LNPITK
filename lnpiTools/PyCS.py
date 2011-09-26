#    This program is part of the University of Minnesota Labratory for
#    NeuroPsychiatric Imaging ToolKit
#
#    LNPITK is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#    Copyright 2011 Brent Nelson

import pygtk; pygtk.require('2.0')
import gtk
import gobject

## backwards-compatibility to 2.4 with python-lxml installed
try:
    import xml.etree.ElementTree as et
except ImportError:
    try:
        import lxml.etree as et
    except ImportError:
        # No module available to meet requirements
        raise

import os as os
import fnmatch as fm
import commands as cmd
from gtk import DrawingArea

# This class from http://jackvalmadre.wordpress.com/2008/09/21/resizable-image-control/
class ResizableImage(DrawingArea):

    def __init__(self, aspect=True, enlarge=False,
            interp=gtk.gdk.INTERP_NEAREST, backcolor=None, max=(1600,1200)):
        """Construct a ResizableImage control.

        Parameters:
        aspect -- Maintain aspect ratio?
        enlarge -- Allow image to be scaled up?
        interp -- Method of interpolation to be used.
        backcolor -- Tuple (R, G, B) with values ranging from 0 to 1,
            or None for transparent.
        max -- Max dimensions for internal image (width, height).

        """
        DrawingArea.__init__(self)
        self.pixbuf = None
        self.aspect = aspect
        self.enlarge = enlarge
        self.connect('expose_event', self.expose)
        self.backcolor = (255, 255, 255)
        self.max = max
        self.interp = interp
        
    def expose(self, widget, event):
        # Load Cairo drawing context.
        self.context = self.window.cairo_create()
        # Set a clip region.
        self.context.rectangle(
            event.area.x, event.area.y,
            event.area.width, event.area.height)
        self.context.clip()
        # Render image.
        self.draw(self.context)
        return False
        
    def draw(self, context):
        # Get dimensions.
        rect = self.get_allocation()
        x, y = rect.x, rect.y
        # Remove parent offset, if any.
        parent = self.get_parent()
        if parent:
            offset = parent.get_allocation()
            x -= offset.x
            y -= offset.y
        # Fill background color.
        if self.backcolor:
            context.rectangle(x, y, rect.width, rect.height)
            context.set_source_rgb(*self.backcolor)
            context.fill_preserve()
        # Check if there is an image.
        if not self.pixbuf:
            return
        width, height = resizeToFit(
            (self.pixbuf.get_width(), self.pixbuf.get_height()),
            (rect.width, rect.height),
            self.aspect,
            self.enlarge)
        x = x + (rect.width - width) / 2
        y = y + (rect.height - height) / 2
        context.set_source_pixbuf(
            self.pixbuf.scale_simple(width, height, self.interp), x, y)
        context.paint()

    def set_from_pixbuf(self, pixbuf):
        width, height = pixbuf.get_width(), pixbuf.get_height()
        # Limit size of internal pixbuf to increase speed.
        if not self.max or (width < self.max[0] and height < self.max[1]):
            self.pixbuf = pixbuf
        else:
            width, height = resizeToFit((width, height), self.max)
            self.pixbuf = pixbuf.scale_simple(
                width, height,
                gtk.gdk.INTERP_BILINEAR)
        self.invalidate()
        
    def set_from_file(self, filename):
        self.set_from_pixbuf(gtk.gdk.pixbuf_new_from_file(filename))

    def invalidate(self):
        self.queue_draw()
        
def resizeToFit(image, frame, aspect=True, enlarge=False):
    """Resizes a rectangle to fit within another.

    Parameters:
    image -- A tuple of the original dimensions (width, height).
    frame -- A tuple of the target dimensions (width, height).
    aspect -- Maintain aspect ratio?
    enlarge -- Allow image to be scaled up?

    """
    if aspect:
        return scaleToFit(image, frame, enlarge)
    else:
        return stretchToFit(image, frame, enlarge)

def scaleToFit(image, frame, enlarge=False):
    image_width, image_height = image
    frame_width, frame_height = frame
    image_aspect = float(image_width) / image_height
    frame_aspect = float(frame_width) / frame_height
    # Determine maximum width/height (prevent up-scaling).
    if not enlarge:
        max_width = min(frame_width, image_width)
        max_height = min(frame_height, image_height)
    else:
        max_width = frame_width
        max_height = frame_height
    # Frame is wider than image.
    if frame_aspect > image_aspect:
        height = max_height
        width = int(height * image_aspect)
    # Frame is taller than image.
    else:
        width = max_width
        height = int(width / image_aspect)
    return (width, height)

def stretchToFit(image, frame, enlarge=False):
    image_width, image_height = image
    frame_width, frame_height = frame
    # Stop image from being blown up.
    if not enlarge:
        width = min(frame_width, image_width)
        height = min(frame_height, image_height)
    else:
        width = frame_width
        height = frame_height
    return (width, height)

class ComponentSelector:
    def __init__(self):
        
        self.COLUMN_COMPONENT_ID = 0
        self.COLUMN_REMOVE = 1
        self.COLUMN_COMMENT = 2

        # older pyGtk doesn't do the string specification
        #bgColor = gtk.gdk.Color('#fff')
        bgColor = gtk.gdk.Color(255, 255, 255)
        
        self.componentFileName = "Components.xml"
        self.folderComponents = ""
        self.needSave = False
        
        # Images to show
        self.imgThresh = ResizableImage()
        self.imgTime = ResizableImage()
        self.imgFreq = ResizableImage()
        
        # Create our treeview store
        # TODO: Move this out into a model class - this will manage the store with load and save methods
        self.store = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_BOOLEAN, gobject.TYPE_STRING)
        
        # Manage component column
        crCompId = gtk.CellRendererText()

        tvcCompId = gtk.TreeViewColumn("Component")
        tvcCompId.pack_start(crCompId, True)
        tvcCompId.add_attribute(crCompId, 'text', self.COLUMN_COMPONENT_ID)

        # Manage removed column
        crRemoved = gtk.CellRendererToggle()
        crRemoved.set_property('activatable', True)
        crRemoved.connect('toggled', self.removed_toggled_cb, self.store)
        
        tvcRemoved = gtk.TreeViewColumn("Removed")
        tvcRemoved.pack_start(crRemoved, True)
        tvcRemoved.add_attribute(crRemoved, 'active', self.COLUMN_REMOVE)
        
        # Manage comment column
        crComment = gtk.CellRendererText()
        crComment.set_property('editable', True)
        crComment.connect('edited', self.comment_edited_cb, self.store)
        
        tvcComment = gtk.TreeViewColumn("Comment")
        tvcComment.pack_start(crComment, True)
        tvcComment.add_attribute(crComment, 'text', self.COLUMN_COMMENT)

        # Create our treeview
        self.tv = gtk.TreeView (self.store)
        self.tv.set_headers_visible(True)
        self.tv.set_rules_hint(True)
        self.tv.get_selection().connect('changed', self.selection_changed)           
        
        # Add cols to the treeview
        self.tv.append_column(tvcCompId)
        self.tv.append_column(tvcRemoved)
        self.tv.append_column(tvcComment)
        self.tv.set_search_column(0);
        #tvcCompId.set_sort_column_id(0);
        
        sw = gtk.ScrolledWindow ()
        sw.set_shadow_type = gtk.SHADOW_ETCHED_IN
        sw.add (self.tv)
     
        btnLoad = gtk.Button("Load")
        btnLoad.set_size_request(-1, 30)
        btnLoad.connect('clicked', self.load_file_clicked)
        
        btnSave = gtk.Button("Save");
        btnSave.set_size_request(-1, 30)
        btnSave.connect('clicked', self.save_file_clicked)

        btnRun = gtk.Button("Run");
        btnRun.set_size_request(-1, 30)
        btnRun.connect('clicked', self.run_clicked)
        
        btnBox = gtk.HBox(True, 0)
        btnBox.pack_start(btnLoad, True, True, 0)
        btnBox.pack_start(btnSave, True, True, 0)
        btnBox.pack_start(btnRun, True, True, 0)
        
        self.txtCmdTemplate = gtk.TextView()
        self.txtCmdTemplate.set_size_request(-1, 75)
        self.txtCmdTemplate.set_border_width(1)
        self.txtCmdTemplate.set_wrap_mode(gtk.WRAP_WORD)
        self.txtCmdTemplate.get_buffer().set_text('fsl_regfilt -i ../../filtered_func_data.nii.gz -o ../../filtered_func_data_denoised -d ../melodic_mix -f \"{components}\"')
        #txtCmdTemplate.MoveCursor += CmdCursorMoved;
        #txtCmdTemplate.InsertAtCursor += CmdCursorInsert;
        #txtCmdTemplate.DeleteFromCursor += CmdCursorDelete;
        
        self.txtGeneratedCmd = gtk.TextView()
        self.txtGeneratedCmd.set_size_request(-1, 175)
        self.txtGeneratedCmd.set_border_width(1)
        self.txtGeneratedCmd.set_wrap_mode(gtk.WRAP_WORD)
        self.txtGeneratedCmd.set_editable(False)

        frmThresh = gtk.Frame()
        frmThresh.add(self.imgThresh)
        frmTime = gtk.Frame()
        frmTime.set_size_request(-1, 173)
        frmTime.add(self.imgTime)
        frmFreq = gtk.Frame()
        frmFreq.set_size_request(-1, 173)
        frmFreq.add(self.imgFreq)

        vertImages = gtk.VBox()
        vertImages.set_size_request(780, 400)
        vertImages.modify_bg(gtk.STATE_NORMAL, bgColor)
        vertImages.pack_start(frmThresh, True, True, 2)
        vertImages.pack_start(frmTime, False, False, 2)
        vertImages.pack_start(frmFreq, False, False, 2)

        vertInfo = gtk.VBox()
        vertInfo.set_size_request(200, -1)
        vertImages.modify_bg(gtk.STATE_NORMAL, bgColor)
        vertInfo.pack_start(sw, True, True, 2)
        vertInfo.pack_start(self.txtCmdTemplate, False, False, 2)
        vertInfo.pack_start(self.txtGeneratedCmd, False, False, 2)
        vertInfo.pack_start(btnBox, False, False, 2)

        
        horizPanes = gtk.HPaned()
        horizPanes.pack1(vertImages, True, True)
        horizPanes.pack2(vertInfo, True, True)

        # Main window setup
        self.win = gtk.Window()
        self.win.props.title = 'PyCS'
        self.win.set_border_width(1)
        #self.win.set_default_size(400, 400) #1024)
        self.win.modify_bg(gtk.STATE_NORMAL, bgColor)
        self.win.set_position(gtk.WIN_POS_CENTER)

        self.win.add(horizPanes)
        self.win.connect("destroy", self.destroy_cb)
        self.win.show_all()
    
    def load_file_clicked(self, args):        
        
        dialog = gtk.FileChooserDialog(title="Recent Documents", parent=self.win, action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                  buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        
        if dialog.run() == gtk.RESPONSE_OK:
            
            self.folderComponents = os.path.dirname(dialog.get_filename())
            self.win.props.title = 'PyCS - ' + self.folderComponents
            os.chdir(self.folderComponents)  
        
            self.selectorFile = os.path.join(self.folderComponents, self.componentFileName)
            if os.path.exists(self.selectorFile):
        
                self.store.clear()
                print 'Loading file: ', self.selectorFile
                analysisTree = et.parse(self.selectorFile)
                components = analysisTree.findall("Components/Component")

                for component in components:
                    id = component.findtext("Id")
                    
                    tmpRem = component.findtext("Remove")
                    if (tmpRem == "true") or (tmpRem == "True"):
                        remove = True
                    else:
                        remove = False
                    
                    comment = component.findtext("Comment")
                    if comment == "None":
                        comment = ""
                    
                    self.store.append(None, (id, remove, comment))
                self.gen_cmd()
                
            else:
                
                print 'No component file found.  Analyzing folder.'
                
                self.store.clear()
                   
                cmps = []
                
                for file in os.listdir(self.folderComponents):
                    
                    if fm.fnmatch(file, 'IC_*_thresh.png'):
                        
                        id = int(file.replace('IC_', '').replace('_thresh.png', ''));
                        cmps.append(id)
                
                cmps.sort()
                
                for cmp in cmps:
                    self.store.append(None, (cmp, False, ''))
        
        self.gen_cmd()
        dialog.destroy()
        
        return

    def gen_cmd(self):
        sb =  ""
        first = True
        
        for treeItm in self.store:
            if treeItm[1] == True:
                
                if first == False:
                    sb = sb + ','
                
                sb = sb + treeItm[0]
                first = False
        
        buf = self.txtCmdTemplate.get_buffer()
        cmd = buf.get_text(buf.get_start_iter(), buf.get_end_iter())
        cmd = cmd.replace("{components}", sb)
        
        self.txtGeneratedCmd.get_buffer().set_text(cmd)

    def selection_changed(self, selection):
        
        model, iter = selection.get_selected()
        
        val = model.get_value(iter, 0)
        
        thre = os.path.join(self.folderComponents, "IC_%s_thresh.png" % val)
        time = os.path.join(self.folderComponents, "t%s.png" % val)
        freq = os.path.join(self.folderComponents, "f%s.png" % val)
        
        self.imgThresh.set_from_pixbuf(gtk.gdk.pixbuf_new_from_file( thre ))
        self.imgTime.set_from_pixbuf( gtk.gdk.pixbuf_new_from_file( time ).subpixbuf(2, 0, 778, 173) )
        self.imgFreq.set_from_pixbuf(gtk.gdk.pixbuf_new_from_file( freq ))
        
        self.gen_cmd()

    def save_file_clicked(self, args):
        #if self.needSave == True:
        sess = et.Element('AnalysisSession')
        
        ver = et.SubElement(sess, 'FileVersion')
        ver.text = "1.0"
        comps = et.SubElement(sess, 'Components')
        
        for treeItm in self.store:
            cmp = et.SubElement(comps, 'Component')
            
            id = et.SubElement(cmp, 'Id')
            id.text = str(treeItm[0])
            
            rem = et.SubElement(cmp, 'Remove')
            rem.text = str(treeItm[1])
            
            cmt = et.SubElement(cmp, 'Comment')
            if cmt != None:
                cmt.text = str(treeItm[2])
            else:
                cmt.text = ""
        
        tree = et.ElementTree(sess)
        
        xmlFile = os.path.join(self.folderComponents, self.componentFileName)
        tree.write(xmlFile)
        print 'Saved File To: ', xmlFile
        
        return

    def run_clicked(self, args):
        
        self.gen_cmd()
        
        buf = self.txtGeneratedCmd.get_buffer()
        cmdStr = buf.get_text(buf.get_start_iter(), buf.get_end_iter())
        
        print 'Running Command: ', cmdStr
        cmdOutput = cmd.getoutput(cmdStr)
        print 'Command Output: ', cmdOutput
        
        self.txtGeneratedCmd.get_buffer().set_text(cmdStr + "\r\n" + cmdOutput)
        
        return

    # Sets the toggled state on the toggle button to true or false.
    def removed_toggled_cb( self, cell, path, model ):
        model[path][1] = not model[path][self.COLUMN_REMOVE]
        self.needSave = True

        return    
    
    # Called when a text cell is edited.  It puts the new text in the 
    # model so that it is displayed properly.
    def comment_edited_cb( self, cell, path, new_text, model ):
        model[path][self.COLUMN_COMMENT] = new_text
        self.needSave = True
        
        return

    # Destroy callback to shutdown the app
    def destroy_cb(self, *kw):
        #if self.needSave == False:
        gtk.main_quit()
        #else:
        #    print 'Must Save First!' # TODO: Change this to a dialog...
        
        return
    
    # Run is called to set off the GTK mainloop
    def run(self):
        
        gtk.main()
        
        return

if __name__ == '__main__':
    cs = ComponentSelector()
    cs.run()
