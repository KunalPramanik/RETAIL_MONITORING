with open("src/app/(dashboard)/page.tsx", "r", encoding="utf-8") as f:
    content = f.read()

# Add import
import_stmt = 'import StreamPlayer from "@/components/cameras/stream-player";\n'
if "StreamPlayer" not in content:
    content = import_stmt + content

# Replace Dashboard's "Live Exit Feeds" grid
old_grid = """<div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {[1, 2, 3, 4].map((cam) => (
                <div key={cam} className="aspect-video bg-gray-900 border border-gray-800 rounded-xl relative overflow-hidden group">
                  <div className="absolute top-4 left-4 z-10 flex gap-2">
                    <span className="px-2 py-1 bg-black/60 backdrop-blur rounded text-xs border border-gray-700 font-mono">CAM-0{cam}</span>
                    <span className="px-2 py-1 bg-red-500/20 text-red-400 backdrop-blur rounded text-xs border border-red-900 flex items-center gap-1 font-bold">
                      <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></div> REC
                    </span>
                  </div>
                  <div className="w-full h-full bg-gray-800 flex items-center justify-center group-hover:bg-gray-750 transition-colors">
                     <Camera size={48} className="text-gray-700" />
                     <p className="absolute bottom-4 text-gray-500 text-sm">Connecting to RTSP Stream...</p>
                  </div>
                </div>
              ))}
            </div>"""

new_grid = """<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {[1, 2, 3, 4].map((cam) => (
                <StreamPlayer key={cam} cameraId={`LANE-${cam}-EXIT`} streamUrl={`rtsp://camera-${cam}/stream`} />
              ))}
            </div>"""

content = content.replace(old_grid, new_grid)

with open("src/app/(dashboard)/page.tsx", "w", encoding="utf-8") as f:
    f.write(content)
