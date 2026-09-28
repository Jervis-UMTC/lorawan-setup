from pathlib import Path
p=Path("lorawan-network-server-gateway/documentation/word-src/06a-chirpstack-first-time-setup.md")
s=p.read_text(encoding="utf-8-sig")
replacements={
    "\u00e2\u20ac\u201d": "-",
    "\u00e2\u2020\u2019": "->",
    "\u00e2\u20ac\u2122": "'",
    "\u00e2\u20ac\u201c": "-",
    "\u0393\u00c7\u00f6": ":",
}
counts={k:s.count(k) for k in replacements}
for old,new in replacements.items():s=s.replace(old,new)
p.write_text(s,encoding="utf-8")
print("ENCODING_REPAIRS",counts)
