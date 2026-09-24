import re

with open("pwa/src/app/gestio/layout.tsx", "r") as f:
    content = f.read()

content = content.replace(
'''        <div className="flex items-center gap-4">
          <Link href="/gestio/mapa" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-emerald-600 flex items-center justify-center font-bold text-white shadow-lg shadow-emerald-600/20">''',
'''        <div className="flex items-center gap-4">
          <Link href="/gestio" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-emerald-600 flex items-center justify-center font-bold text-white shadow-lg shadow-emerald-600/20">'''
)

with open("pwa/src/app/gestio/layout.tsx", "w") as f:
    f.write(content)

print("Logo link fixed")
