# update_vcv_ch_gate.py
import os, sys
from td import *

def update():
    print("[vcv_gate] Updating vcv_zmq_bridge and pong_chop_exec for 0-10V CH1-CH9 outputs...")

    v = op('/project1/vcv_zmq_bridge')
    if not v:
        v = op('/project1').loadTox('E:/TD Projects/vcv_zmq_bridge.tox')

    if not v:
        print("[error] Could not find /project1/vcv_zmq_bridge!")
        return

    # 1. Update vcv_bridge_ext DAT text
    ext_dat = v.op('vcv_bridge_ext')
    if ext_dat:
        ext_dat.text = """# VcvBridgeExt
import sys, os
for _p in ["E:/TD Projects/.py/site-packages", os.path.abspath(os.path.join(project.folder, '../.py/site-packages')), os.path.abspath(os.path.join(project.folder, '.py/site-packages'))]:
    if os.path.exists(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
import zmq
import struct

class VcvBridgeExt:
    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.context = None
        self.socket = None
        self.cv = [0.0] * 9  # 9 Direct CV Channels (0..10V for CH1..CH9)
        self.midi_pitch = [0.0] * 16
        self.midi_gate = [0.0] * 16
        self.midi_vel = [0.0] * 16
        self.voice_notes = [-1] * 16
        self.voice_age = [0] * 16
        self.age_counter = 0
        self.UpdateConnection()

    def UpdateConnection(self):
        self.CloseConnection()
        active = self.ownerComp.par.Active.eval()
        if not active:
            return
        address = self.ownerComp.par.Address.eval()
        port = self.ownerComp.par.Port.eval()
        proto = self.ownerComp.par.Protocol.eval()
        try:
            self.context = zmq.Context()
            if proto == "pub":
                self.socket = self.context.socket(zmq.PUB)
            else:
                self.socket = self.context.socket(zmq.PUSH)
            self.socket.connect(f"tcp://{address}:{port}")
            print(f"ZMQ Bridge connected to tcp://{address}:{port} ({proto.upper()})")
        except Exception as e:
            print(f"ZMQ Bridge Connection Error: {e}")

    def CloseConnection(self):
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        if self.context:
            try:
                self.context.term()
            except:
                pass
            self.context = None

    def TriggerCV(self, ch_idx, voltage=10.0):
        if 0 <= ch_idx < 9:
            self.cv[ch_idx] = float(voltage)

    def ClearCV(self, ch_idx=None):
        if ch_idx is None:
            self.cv = [0.0] * 9
        elif 0 <= ch_idx < 9:
            self.cv[ch_idx] = 0.0

    def PlayNote(self, note_num, velocity=8.0):
        pass

    def ReleaseNote(self, note_num):
        pass

    def ClearAll(self):
        self.cv = [0.0] * 9
        for i in range(16):
            self.midi_gate[i] = 0.0
            self.voice_notes[i] = -1
"""

    # 2. Update script_zmq_code DAT text
    code_dat = v.op('script_zmq_code')
    if code_dat:
        code_dat.text = """import sys, os
for _p in ["E:/TD Projects/.py/site-packages", os.path.abspath(os.path.join(project.folder, '../.py/site-packages')), os.path.abspath(os.path.join(project.folder, '.py/site-packages'))]:
    if os.path.exists(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
import struct
import zmq

def onCook(scriptOp):
    scriptOp.clear()
    ext = None
    try:
        ext = parent().ext.VcvBridgeExt
    except AttributeError:
        pass
    if not ext:
        try:
            ext = parent().ext[0]
        except:
            pass
    if not ext:
        return
    
    # 1. Get 9 CV channels from Ext or Input 1
    cv = list(ext.cv) if hasattr(ext, 'cv') else [0.0] * 9
    if len(scriptOp.inputs) > 0:
        in_chop = scriptOp.inputs[0]
        for i in range(min(9, in_chop.numChans)):
            cv[i] = max(cv[i], in_chop[i][0])
    
    midi_pitch = list(ext.midi_pitch)
    midi_gate = list(ext.midi_gate)
    midi_vel = list(ext.midi_vel)
    
    # 2. Pack and send 57 floats (CH1..CH9 CV + poly channels)
    if parent().par.Active.eval() and ext.socket:
        payload = struct.pack('<57f', *cv, *midi_pitch, *midi_gate, *midi_vel)
        try:
            ext.socket.send(payload, zmq.NOBLOCK)
        except zmq.Again:
            pass
"""

    # 3. Update exec_frame_cook to decay gate pulses back to 0V
    exec_dat = v.op('exec_frame_cook')
    if not exec_dat:
        exec_dat = v.create(executeDAT, 'exec_frame_cook')
        exec_dat.nodeX = 0
        exec_dat.nodeY = 250
    exec_dat.par.framestart = True
    exec_dat.text = """# exec_frame_cook
def onFrameStart(frame):
    try:
        v = op('/project1/vcv_zmq_bridge')
        if v and hasattr(v.ext, 'VcvBridgeExt'):
            ext = v.ext.VcvBridgeExt
            # Decay gate voltages to 0.0V for pulse triggers
            for i in range(9):
                if ext.cv[i] > 0:
                    ext.cv[i] = max(0.0, ext.cv[i] - 2.5)
        sz = op('/project1/vcv_zmq_bridge/script_zmq')
        if sz:
            sz.cook(force=True)
    except:
        pass
    return
"""

    # Reinit extension
    v.par.reinitextensions.pulse()
    print("[vcv_gate] vcv_zmq_bridge updated to stream CH1-CH9 0-10V CV outputs!")

update()
