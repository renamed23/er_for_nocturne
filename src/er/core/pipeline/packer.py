from er.utils.binary import BinaryReader
from er.utils.console import console
from er.utils.fs import PathLike, to_path
from er.utils.misc import write_json


def unpack(input_path: PathLike, out_dir: PathLike) -> None:
    """
    解包。

    Args:
        input_path: 输入包路径。
        out_dir: 解包输出目录。

    Returns:
        None
    """

    source = to_path(input_path)
    output_dir = to_path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. 准备读取器
    exe_file = source.with_suffix(".exe")
    if not exe_file.exists():
        raise FileNotFoundError(f"找不到对应的 EXE: {exe_file}")
    
    exe_data = exe_file.read_bytes()
    pack_data = source.read_bytes()

    # from pathlib import Path
    # decrypted = bytearray(pack_data)
    # for j in range(len(decrypted)):
    #     decrypted[j] ^= 0x55
    # Path("workspace/decoded.bin").write_bytes(decrypted)
    
    exe_reader = BinaryReader(exe_data)
    pack_reader = BinaryReader(pack_data)

    # --- 2. 静态解析 PE 结构 (获取地址转换所需数据) ---
    # 定位 PE Header
    exe_reader.seek(0x3C)
    pe_offset = exe_reader.read_u32()
    
    # 获取 ImageBase (PE32 偏移 0x34)
    exe_reader.seek(pe_offset + 0x34)
    image_base = exe_reader.read_u32()
    
    # 获取段数量
    exe_reader.seek(pe_offset + 0x06)
    num_sections = exe_reader.read_u16()
    
    # 获取 OptionalHeader 大小以定位段表
    exe_reader.seek(pe_offset + 0x14)
    size_of_opt = exe_reader.read_u16()
    
    section_table_offset = pe_offset + 0x18 + size_of_opt
    
    # 建立段映射表
    sections = []
    exe_reader.seek(section_table_offset)
    for _ in range(num_sections):
        _name = exe_reader.read_bytes(8)
        v_size = exe_reader.read_u32()
        v_addr = exe_reader.read_u32() # RVA
        r_size = exe_reader.read_u32()
        r_offset = exe_reader.read_u32() # PointerToRawData
        exe_reader.seek(16, 1) # 跳过无用字段
        sections.append((v_addr, v_size, r_offset))

    def va_to_file_offset(va: int) -> int:
        rva = va - image_base
        for s_vaddr, s_vsize, s_roffset in sections:
            if s_vaddr <= rva < s_vaddr + s_vsize:
                return rva - s_vaddr + s_roffset
        raise ValueError(f"无法映射 VA: 0x{va:X}")

    # --- 3. 解析 1036 个 PackEntry ---
    entry_start_va = 0x437CEC
    entry_count = 1036
    
    exe_reader.seek(va_to_file_offset(entry_start_va))
    
    entries = []
    for _ in range(entry_count):
        name_va = exe_reader.read_u32()
        file_offset = exe_reader.read_u32()
        flag = exe_reader.read_u32()
        
        temp_pos = exe_reader.tell()
        exe_reader.seek(va_to_file_offset(name_va))

        name = exe_reader.read_str()
        exe_reader.seek(temp_pos)
        
        entries.append({
            "name": name,
            "offset": file_offset,
            "flag": flag
        })

    for i in range(entry_count):
        entry = entries[i]

        start_pos = entry["offset"]
        
        if i < entry_count - 1:
            size = entries[i+1]["offset"] - start_pos
        else:
            size = len(pack_data) - start_pos
            
        assert size > 0

        pack_reader.seek(start_pos)
        raw_bytes = pack_reader.read_bytes(size)
        
        decrypted = bytearray(raw_bytes)
        for j in range(len(decrypted)):
            decrypted[j] ^= 0x55

        if decrypted.startswith(bytes.fromhex("AA 8D AA B5 55 45 1F")):
            continue
        if decrypted.startswith(bytes.fromhex("17 18")):
            continue

        target_path = output_dir / entry["name"]
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(decrypted)

    write_json(source.with_suffix(".json"), {item["name"]:str(item["offset"]) for item in entries})

    console.print(
        f"[OK] unpack 完成: {source} -> {output_dir} (共 {entry_count} 个文件已解密)",
        style="info",
    )


def pack(input_dir: PathLike, out_path: PathLike) -> None:
    """
    将目录内容重新打包。

    Args:
        input_dir: 输入目录路径。
        out_path: 输出包路径。

    Returns:
        None

    Raises:
        ValueError: 输入非法、命名冲突或字段超限。
    """
    input_root = to_path(input_dir)
    output_path = to_path(out_path)
    if not input_root.is_dir():
        raise ValueError(f"输入目录不存在: {input_root}")

    # TODO

    console.print(
        f"[OK] pack 完成: {input_root} -> {output_path}",
        style="info",
    )
