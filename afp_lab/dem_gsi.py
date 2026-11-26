"""GSI elevation tile adapter; v0.5 cache format unchanged."""
from pathlib import Path
import hashlib, math, struct, urllib.request, urllib.error, zlib

BASE='https://cyberjapandata.gsi.go.jp/xyz'
SOURCES=(('dem5a_png',15),('dem5b_png',15),('dem5c_png',15),('dem_png',14))

def decode_png(data):
    """GSI specification: 256x256, 8-bit RGB; signed 24-bit centimetres."""
    if data[:8]!=b'\x89PNG\r\n\x1a\n': raise ValueError('Not a PNG tile')
    i=8; parts=[]; header=None; ended=False
    while i+12<=len(data):
        length,tag=struct.unpack_from('>I4s',data,i); end=i+12+length
        if end>len(data): raise ValueError('Truncated PNG')
        chunk=data[i+8:i+8+length]
        if zlib.crc32(tag+chunk)!=struct.unpack_from('>I',data,i+8+length)[0]: raise ValueError('PNG CRC mismatch')
        if tag==b'IHDR': header=struct.unpack('>IIBBBBB',chunk)
        elif tag==b'IDAT': parts.append(chunk)
        elif tag==b'IEND': ended=True; break
        i=end
    if not ended or header!=(256,256,8,2,0,0,0): raise ValueError(f'Unsupported GSI PNG format: {header}')
    raw=zlib.decompress(b''.join(parts)); stride=768
    if len(raw)!=256*(stride+1): raise ValueError('Wrong PNG raster size')
    result=[]; prev=bytearray(stride)
    for y in range(256):
        off=y*(stride+1); f=raw[off]; row=bytearray(raw[off+1:off+1+stride])
        if f>4: raise ValueError('Invalid PNG filter')
        for j in range(stride):
            a=row[j-3] if j>=3 else 0; b=prev[j]; c=prev[j-3] if j>=3 else 0
            if f==1: p=a
            elif f==2: p=b
            elif f==3: p=(a+b)//2
            elif f==4:
                q=a+b-c; pa,pb,pc=abs(q-a),abs(q-b),abs(q-c)
                p=a if pa<=pb and pa<=pc else b if pb<=pc else c
            else: p=0
            row[j]=(row[j]+p)&255
        vals=[]
        for j in range(0,stride,3):
            v=(row[j]<<16)|(row[j+1]<<8)|row[j+2]
            vals.append(None if v==0x800000 else (v if v<0x800000 else v-0x1000000)/100)
        result.append(vals); prev=row
    return result

def pixel(lat,lon,z):
    if not (-85<lat<85 and -180<=lon<180): raise ValueError('Coordinates outside tile range')
    n=256*2**z
    return int((lon+180)/360*n),int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n)

class GsiDEM:
    def __init__(self, cache, offline=False):
        self.cache=Path(cache);self.offline=offline;self.tiles={};self.provenance={}
    def tile(self,layer,z,x,y):
        key=f'{layer}/{z}/{x}/{y}'; path=self.cache/(key+'.png'); missing=path.with_suffix('.missing')
        if key in self.tiles:return self.tiles[key]
        url=f'{BASE}/{key}.png'
        if path.is_file():data=path.read_bytes()
        elif missing.is_file():self.tiles[key]=None;return None
        elif self.offline:raise ValueError(f'Offline cache missing {key}; run once online')
        else:
            print(f'GSI download: {key}',flush=True)
            req=urllib.request.Request(url,headers={'User-Agent':'AFP-Lab/0.4 terrain research'})
            try:
                with urllib.request.urlopen(req,timeout=20) as r:data=r.read(2_000_001)
            except urllib.error.HTTPError as e:
                if e.code not in (404,410):raise
                path.parent.mkdir(parents=True,exist_ok=True);missing.write_text('HTTP '+str(e.code),encoding='utf-8');self.tiles[key]=None;return None
            if len(data)>2_000_000:raise ValueError('Oversize DEM tile')
            decode_png(data) # never cache a corrupt response
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        raster=decode_png(data);self.tiles[key]=raster
        self.provenance[key]={'url':url,'sha256':hashlib.sha256(data).hexdigest(),'layer':layer}
        return raster
    def sample(self,lat,lon):
        for layer,z in SOURCES:
            px,py=pixel(lat,lon,z); tile=self.tile(layer,z,px//256,py//256)
            if tile is not None and tile[py%256][px%256] is not None:return tile[py%256][px%256]
        raise ValueError(f'No GSI elevation data at {lat:.6f},{lon:.6f}; cannot assume zero elevation')

