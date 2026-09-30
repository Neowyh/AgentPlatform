/* gb_log_parse.c — 试验日志解析模块（本文件为 GB18030 编码，评测用伪数据）
 * 验收点：read_file/grep 按编码嗅探顺序 UTF-8 → UTF-8 BOM → GB18030 读取，
 * 中文注释与日志字段不得因编码报错丢失。
 */
#include <stdio.h>

/* 从试验日志中提取“报警时刻”与“通道号”两列。 */
int parse_alarm_record(const char *line, int *channel, double *seconds)
{
    /* 典型日志行：“12:03:41 通道 HF-07 热流超限” */
    if (line == NULL || channel == NULL || seconds == NULL) {
        return -1;
    }
    return sscanf(line, "%*d:%*d:%*d 通道 %d 热流超限 %lf", channel, seconds) - 1;
}

const char *alarm_level_name(int level)
{
    switch (level) {
    case 0: return "正常";
    case 1: return "预警";
    case 2: return "超限";
    default: return "未知";
    }
}
