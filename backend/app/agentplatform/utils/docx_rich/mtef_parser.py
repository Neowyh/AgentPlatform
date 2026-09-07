"""
MathType MTEF 公式解析器

基于 MTEF-py 库从 MathType OLE 对象中提取公式并转换为 LaTeX。

数据流:
  docx (ZIP) → word/embeddings/oleObjectN.bin (OLE Compound File)
    → MTEF-py 解析 → LaTeX 字符串

MTEF-py 失败时返回空结果，由上层（docx_parser）降级为 MFR 模型识别。
"""

import logging
import re
import zipfile

from lxml import etree

logger = logging.getLogger(__name__)

try:
    from .mtef_py.mtef import MTEF

    _HAS_MTEF_PY = True
except ImportError:
    _HAS_MTEF_PY = False


def _clean_latex(raw: str) -> str:
    """
    清理 MTEF-py 输出的 LaTeX

    - 去除 $ 包裹
    - 压缩多余空格
    - 去除空 {} 残留
    """
    if not raw:
        return ""
    s = raw.strip()
    # 去除 $ 包裹
    if s.startswith("$") and s.endswith("$") and len(s) > 1:
        s = s[1:-1].strip()
    # 压缩连续空格
    s = re.sub(r"  +", " ", s)
    # 去除 \left 和 \right 后多余的空格
    s = re.sub(r"\\left\s+", r"\\left", s)
    s = re.sub(r"\\right\s+", r"\\right", s)
    s = s.strip()
    return s


def _parse_ole_to_latex(ole_bin: bytes) -> str | None:
    """
    用 MTEF-py 从 OLE bin 数据中解析公式为 LaTeX

    Args:
        ole_bin: oleObject*.bin 的完整二进制数据

    Returns:
        LaTeX 字符串，失败返回 None
    """
    if not _HAS_MTEF_PY:
        return None

    try:
        eqn, err = MTEF.OpenBytes(ole_bin)
        if err is not None:
            return None
        if eqn is None:
            return None

        latex = eqn.Translate()
        if not latex or not latex.strip():
            return None

        return _clean_latex(latex)
    except Exception as e:
        logger.debug(f"MTEF-py 解析异常: {e}")
        return None


def extract_latex_from_docx(docx_path: str) -> dict[str, str]:
    """
    从 docx 文件中提取所有 MathType OLE 公式为 LaTeX

    返回 {img_rId: latex_string} 映射。
    img_rId 是 document.xml 中 v:imagedata 引用缩略图的关系 ID。

    Args:
        docx_path: docx 文件路径

    Returns:
        {img_rId: latex_string} 字典
    """
    if not _HAS_MTEF_PY:
        logger.debug("MTEF-py 库不可用，跳过 MTEF 解析")
        return {}

    result = {}

    try:
        with zipfile.ZipFile(docx_path, "r") as z:
            # 1. 从 document.xml.rels 获取 OLE rId -> bin 文件名映射
            rels_map = {}  # ole_rId -> target filename
            try:
                with z.open("word/_rels/document.xml.rels") as f:
                    rels_tree = etree.parse(f)
                    ns = "http://schemas.openxmlformats.org/package/2006/relationships"
                    for rel in rels_tree.findall(f".//{{{ns}}}Relationship"):
                        rel_type = rel.get("Type", "")
                        if "oleObject" in rel_type:
                            rId = rel.get("Id")
                            target = rel.get("Target")
                            if rId and target:
                                rels_map[rId] = target
            except KeyError:
                pass

            if not rels_map:
                return {}

            # 2. 从 document.xml 获取 img_rId -> ole_rId 映射
            img_to_ole = {}  # img_rId -> ole_rId
            ns_w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            ns_v = "urn:schemas-microsoft-com:vml"
            ns_o = "urn:schemas-microsoft-com:office:office"
            ns_r = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

            try:
                with z.open("word/document.xml") as f:
                    doc_tree = etree.parse(f)
                    for w_obj in doc_tree.getroot().findall(f".//{{{ns_w}}}object"):
                        img_rid = None
                        ole_rid = None

                        imagedata = w_obj.find(f".//{{{ns_v}}}imagedata")
                        if imagedata is not None:
                            img_rid = imagedata.get(f"{{{ns_r}}}id")

                        ole_elem = w_obj.find(f".//{{{ns_o}}}OLEObject")
                        if ole_elem is not None:
                            prog_id = ole_elem.get("ProgID", "")
                            if "Equation" in prog_id:
                                ole_rid = ole_elem.get(f"{{{ns_r}}}id")

                        if img_rid and ole_rid:
                            img_to_ole[img_rid] = ole_rid
            except KeyError:
                pass

            # 3. 提取每个 OLE bin 并用 MTEF-py 解析
            ole_to_latex = {}  # ole_rId -> latex
            for ole_rid, target in rels_map.items():
                bin_path = f"word/{target}"
                try:
                    ole_bin = z.read(bin_path)
                    latex = _parse_ole_to_latex(ole_bin)
                    if latex:
                        ole_to_latex[ole_rid] = latex
                        logger.debug(f"MTEF-py 解析成功 [{ole_rid}]: {latex[:50]}...")
                except KeyError:
                    pass

            # 4. 转换为 img_rId -> latex（与 docx_parser 的 latex_map 键一致）
            for img_rid, ole_rid in img_to_ole.items():
                if ole_rid in ole_to_latex:
                    result[img_rid] = ole_to_latex[ole_rid]

        if result:
            logger.info(f"MTEF-py 解析: {len(result)} 个公式成功转为 LaTeX")
        else:
            logger.debug("MTEF-py 未解析到任何公式")

    except Exception as e:
        logger.warning(f"从 docx 提取 MTEF 公式失败: {e}")

    return result
