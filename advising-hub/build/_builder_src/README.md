# build_advising_hub.py — source parts

`build_advising_hub.py` (the single-file dashboard builder, ~155 KB) is stored here as ordered
byte-exact slices because it exceeded the single-file commit size limit of the publishing tool.
Concatenate the parts in name order to reconstruct the exact original:

```sh
cat part_01a.txt part_01b.txt part_02.txt part_03.txt part_04.txt part_05.txt > ../build_advising_hub.py
```

Verify — the reconstructed file's git blob SHA must equal:

```
78109c27519e6a9959064c9bfb8b63a2dfedc177
```

(`git hash-object build_advising_hub.py`). Each part was verified byte-exact against its source
line range (part_01a = lines 1–380, part_01b = 381–760, part_02 = 761–1180, part_03 = 1181–1600,
part_04 = 1601–1960, part_05 = 1961–2301). See `../REBUILD.md` for the full rebuild specification.
