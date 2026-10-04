# Fix page.tsx
with open("src/app/(dashboard)/page.tsx", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.strip() == 'import StreamPlayer from "@/components/cameras/stream-player";':
        continue
    new_lines.append(line)

for i, line in enumerate(new_lines):
    if "use client" in line:
        new_lines.insert(i + 1, 'import StreamPlayer from "@/components/cameras/stream-player";\n')
        break

with open("src/app/(dashboard)/page.tsx", "w", encoding="utf-8") as f:
    f.writelines(new_lines)


# Fix layout.tsx
with open("src/app/(dashboard)/layout.tsx", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('import "./globals.css";', 'import "../globals.css";')

with open("src/app/(dashboard)/layout.tsx", "w", encoding="utf-8") as f:
    f.write(content)
