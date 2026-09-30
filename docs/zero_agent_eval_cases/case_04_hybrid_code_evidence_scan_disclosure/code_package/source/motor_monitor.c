/* motor_monitor.c — 电机监测采集模块（评测伪数据，非真实型号代码）
 * 已知缺陷（用于静态扫描验收）：status_label() 的入参上界校验写成 > 4，
 * 而 STATUS_LABELS 只有 3 个元素——cppcheck 应报 arrayIndexOutOfBounds 类告警。
 */
#include <string.h>

static const char *STATUS_LABELS[3] = {"nominal", "drift", "over-limit"};

const char *status_label(int status)
{
    if (status < 0 || status > 4) {
        return "invalid";
    }
    return STATUS_LABELS[status];
}

int status_from_raw(int raw, int threshold)
{
    if (raw > threshold * 2) {
        return 2;
    }
    if (raw > threshold) {
        return 1;
    }
    return 0;
}
