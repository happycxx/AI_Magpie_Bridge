"""ClipboardFeedbackMixin — clipboard auto-apply, feedback, and status display."""
import os
import datetime
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer
from core.replace_engine import (
    normalize_replace_block_text,
    extract_replace_blocks,
    build_replace_blocks_signature,
)


class ClipboardFeedbackMixin:
    """Clipboard monitoring, auto-apply, and AI feedback generation."""

    def _t(self, key, fallback="", **kwargs):
        """Safe translation helper for this mixin."""
        if hasattr(self, "tr_text"):
            try:
                return self.tr_text(key, **kwargs)
            except Exception:
                pass

        if kwargs and fallback:
            try:
                return fallback.format(**kwargs)
            except Exception:
                return fallback
        return fallback or key

    def _paste_ai_input_from_context_menu(self):
        self.text_ai_input.paste()
        self.add_operation_log(
            self._t("clipboard.log.pasted_to_ai_input", "已从剪贴板粘贴到右侧输入区"),
            "info")

    def clear_ai_input(self):
        if hasattr(self, "text_ai_input"):
            self.text_ai_input.clear()
        self.clear_failed_feedback()
        self.add_operation_log(
            self._t("clipboard.log.cleared_ai_input", "已清空右侧输入内容"),
            "info")

    def add_operation_log(self, text, level="info"):
        if hasattr(self, "floating_status_widget"):
            try:
                self.floating_status_widget.update_status(text, level)
            except Exception:
                pass

        if not hasattr(self, "operation_log_list"):
            return

        icon_map = {"info": "●", "success": "●", "warning": "●", "error": "●"}
        icon = icon_map.get(level, "●")
        time_text = datetime.datetime.now().strftime("%H:%M:%S")
        self.operation_log_list.addItem(f"{icon}  {time_text}  {text}")

        max_items = 80
        while self.operation_log_list.count() > max_items:
            self.operation_log_list.takeItem(0)

        self.operation_log_list.scrollToBottom()

    def apply_clipboard_auto_state(self, enabled, persist=False):
        self.clipboard_auto_enabled = bool(enabled)
        self.btn_auto_clipboard.setChecked(self.clipboard_auto_enabled)

        if persist:
            self.settings["clipboard_auto_enabled"] = self.clipboard_auto_enabled
            self.save_settings()

        if self.clipboard_auto_enabled:
            self.btn_auto_clipboard.setText(
                self.tr_text("button.auto_clipboard.on") if hasattr(self, "tr_text") else "📋 监听：开")
            self.btn_auto_clipboard.setStyleSheet(
                "background-color: #67C23A; color: white; border: none; font-weight: bold;")
            self.last_clipboard_text = self.clipboard.text()
            self.update_auto_status(
                self._t("clipboard.status.on_waiting", "自动监听：开启，等待剪贴板"),
                "#67C23A", "#F0F9EB")
        else:
            self.btn_auto_clipboard.setText(
                self.tr_text("button.auto_clipboard.off") if hasattr(self, "tr_text") else "📋 监听：关")
            self.btn_auto_clipboard.setStyleSheet("")
            self.last_clipboard_text = self.clipboard.text()
            self.update_auto_status(
                self._t("clipboard.status.off", "自动监听：关闭"),
                "#909399", "#F4F4F5")

    def toggle_clipboard_auto_apply(self):
        self.apply_clipboard_auto_state(self.btn_auto_clipboard.isChecked(), persist=True)

    def check_clipboard_auto_apply(self):
        if not self.clipboard_auto_enabled:
            return

        tab = self.current_tab()
        if not tab:
            self.update_auto_status(
                self._t("clipboard.status.no_file", "自动监听：开启，跳过（当前无文件）"),
                "#E6A23C", "#FDF6EC")
            return

        try:
            clipboard_text = normalize_replace_block_text(self.clipboard.text())
        except Exception:
            self.update_auto_status(
                self._t("clipboard.status.read_failed", "自动监听：开启，异常（读取剪贴板失败）"),
                "#F56C6C", "#FEF0F0")
            return

        if not clipboard_text or not clipboard_text.strip():
            self.update_auto_status(
                self._t("clipboard.status.on_waiting", "自动监听：开启，等待剪贴板"),
                "#67C23A", "#F0F9EB")
            return

        if clipboard_text == self.last_clipboard_text:
            return

        self.last_clipboard_text = clipboard_text
        self.add_operation_log(
            self._t("clipboard.log.detected_change", "剪贴板内容检测到修改"),
            "info")
        self.update_feedback_hint(
            self._t("feedback.checking", "正在检查你刚复制的 AI 替换内容……"),
            "neutral")

        clipboard_signature = build_replace_blocks_signature(clipboard_text)

        if clipboard_signature and clipboard_signature == self.last_auto_applied_signature:
            self.last_auto_applied_text = clipboard_text
            self.update_auto_status(
                self._t("clipboard.status.already_applied", "自动监听：开启，跳过（该内容已自动应用）"),
                "#909399", "#F4F4F5")
            return

        if clipboard_signature and clipboard_signature == self.last_auto_skipped_signature:
            self.last_auto_skipped_text = clipboard_text
            self.update_auto_status(
                self._t("clipboard.status.already_skipped", "自动监听：开启，跳过（该内容已判定无需处理）"),
                "#909399", "#F4F4F5")
            return

        if not clipboard_signature:
            if hasattr(self, "text_ai_input"):
                self.text_ai_input.setPlainText(clipboard_text)
            if hasattr(self, "preview_panel"):
                self.preview_panel.clear()
            self.last_auto_skipped_text = clipboard_text
            self.last_auto_skipped_signature = ""
            self.cache_failed_feedback("invalid_block", clipboard_text, {"reason": "invalid_block"})
            self.update_auto_status(
                self._t("clipboard.status.invalid_block", "自动监听：开启，跳过（格式不匹配，可反馈给AI）"),
                "#E6A23C", "#FDF6EC")
            return

        applied = self.apply_ai_changes(
            silent=True, content_override=clipboard_text,
            require_unique_match=True, return_details=True)

        if applied.get("success"):
            self.last_auto_applied_text = clipboard_text
            self.last_auto_applied_signature = clipboard_signature
            if hasattr(self, "text_ai_input"):
                try:
                    self.text_ai_input.blockSignals(True)
                    self.text_ai_input.clear()
                finally:
                    self.text_ai_input.blockSignals(False)
            if hasattr(self, "preview_panel"):
                self.preview_panel.clear()
                self.preview_panel.setVisible(False)
            self.clear_failed_feedback()
            self.add_operation_log(
                self._t("clipboard.log.auto_success", "自动替换成功并已保存"),
                "success")
            self.update_feedback_hint(
                self._t(
                    "feedback.auto_success",
                    "✅ {time} 自动替换成功，已保存。",
                    time=datetime.datetime.now().strftime("%H:%M:%S")),
                "success")
            self.update_auto_status(
                self._t("clipboard.status.apply_success", "自动监听：开启，自动应用成功"),
                "#67C23A", "#F0F9EB")
        else:
            if hasattr(self, "text_ai_input"):
                self.text_ai_input.setPlainText(clipboard_text)
            self.last_auto_skipped_text = clipboard_text
            self.last_auto_skipped_signature = clipboard_signature
            self.add_operation_log(
                self._t("clipboard.log.auto_failed_feedback_ready", "自动替换未成功，已生成反馈入口"),
                "warning")
            self.cache_failed_feedback(
                applied.get("reason", "replace_failed"), clipboard_text, applied)

            if applied.get("reason") == "unique_match_failed" and applied.get("multi_match_failed"):
                self.update_auto_status(
                    self._t("clipboard.status.multi_match", "自动监听：开启，跳过（命中多处，可反馈给AI）"),
                    "#E6A23C", "#FDF6EC")
            elif applied.get("zero_match_failed"):
                self.update_auto_status(
                    self._t("clipboard.status.zero_match", "自动监听：开启，跳过（未命中代码，可反馈给AI）"),
                    "#E6A23C", "#FDF6EC")
            else:
                self.update_auto_status(
                    self._t("clipboard.status.replace_failed", "自动监听：开启，跳过（替换失败，可反馈给AI）"),
                    "#E6A23C", "#FDF6EC")

    def update_auto_status(self, text, color="#909399", bg="#F4F4F5"):
        normalized_text = (text or "").lower()

        success_markers = ("成功", "succeeded", "success", "applied")
        error_markers = ("异常", "失败", "error", "failed")
        warning_markers = (
            "跳过", "格式不匹配", "无文件", "命中失败", "已跳过", "已应用过",
            "skipped", "mismatch", "no current file", "no file", "not found",
            "multiple", "already", "format"
        )
        neutral_markers = ("关闭", "off")

        floating_level = "info"
        if any(marker in normalized_text for marker in success_markers):
            floating_level = "success"
        elif any(marker in normalized_text for marker in error_markers):
            floating_level = "error"
        elif any(marker in normalized_text for marker in warning_markers):
            floating_level = "warning"
        elif any(marker in normalized_text for marker in neutral_markers):
            floating_level = "neutral"

        if hasattr(self, "floating_status_widget"):
            try:
                self.floating_status_widget.update_status(text, floating_level)
            except Exception:
                pass

        if hasattr(self, "lbl_auto_status"):
            short_text = text
            replacements = {
                "自动监听：": "", "开启，": "", "跳过（": "跳过:",
                "）": "", "自动应用成功": self._t("clipboard.status.short.applied", "应用成功"),
                "等待剪贴板": self._t("clipboard.status.short.waiting", "等待剪贴板"),
                "关闭": self._t("clipboard.status.short.off", "监听关闭"),
                "异常（读取剪贴板失败）": self._t("clipboard.status.short.read_failed", "读取失败"),
                "该内容已自动应用": self._t("clipboard.status.short.already_applied", "已应用过"),
                "该内容已判定无需处理": self._t("clipboard.status.short.already_skipped", "已跳过"),
                "格式不匹配": self._t("clipboard.status.short.invalid_block", "格式不匹配"),
                "当前无文件": self._t("clipboard.status.short.no_file", "无文件"),
                "窗口未激活": self._t("clipboard.status.short.window_inactive", "窗口未激活"),
                "唯一命中失败或替换失败": self._t("clipboard.status.short.match_failed", "命中失败"),
                "Auto monitor:": "",
                "on,": "",
                "off": self._t("clipboard.status.short.off", "监听关闭"),
                "waiting for clipboard": self._t("clipboard.status.short.waiting", "等待剪贴板"),
                "auto apply succeeded": self._t("clipboard.status.short.applied", "应用成功"),
                "failed to read clipboard": self._t("clipboard.status.short.read_failed", "读取失败"),
                "already auto applied": self._t("clipboard.status.short.already_applied", "已应用过"),
                "already marked as no action needed": self._t("clipboard.status.short.already_skipped", "已跳过"),
                "format mismatch": self._t("clipboard.status.short.invalid_block", "格式不匹配"),
                "no current file": self._t("clipboard.status.short.no_file", "无文件"),
                "code not found": self._t("clipboard.status.short.match_failed", "命中失败"),
                "matched multiple places": self._t("clipboard.status.short.match_failed", "命中失败"),
                "replace failed": self._t("clipboard.status.short.match_failed", "命中失败"),
            }
            for old, new in replacements.items():
                short_text = short_text.replace(old, new)

            self.lbl_auto_status.setText(short_text)
            self.lbl_auto_status.setToolTip(text)
            self.lbl_auto_status.setStyleSheet(
                f"color: {color}; font-size: 12px; padding: 2px 6px; "
                f"background: {bg}; border-radius: 6px;")

            duration = 900
            state = "none"

            if any(marker in normalized_text for marker in success_markers):
                state = "success"
                duration = 900
            elif any(marker in normalized_text for marker in error_markers):
                state = "error"
                duration = 1200
            elif any(marker in normalized_text for marker in warning_markers):
                state = "warning"
                duration = 900
            elif "等待剪贴板" in text or "waiting" in normalized_text:
                state = "none"
                duration = 0
            elif any(marker in normalized_text for marker in neutral_markers):
                state = "none"
                duration = 0

            if state == "none":
                self.clear_window_flash_state()
            else:
                self.set_window_flash_state(state, duration)

    def refresh_window_style(self):
        if hasattr(self, "main_container"):
            self.main_container.update()

    def set_window_flash_state(self, state, duration=900):
        if hasattr(self, "floating_status_widget") and state != "none":
            try:
                self.floating_status_widget.update_status(
                    self.floating_status_widget.status_label.text(),
                    state
                )
            except Exception:
                pass

        if not hasattr(self, "main_container"):
            return

        color_map = {"success": "#22C55E", "warning": "#F59E0B",
                     "error": "#EF4444", "none": "#E8EEF7"}
        border_color = color_map.get(state, "#E8EEF7")

        if state == "none":
            self.clear_window_flash_state()
            return

        self.main_container.setStyleSheet(f"""
            QFrame#main_container {{
                background-color: #FFFFFF;
                border: 2px solid {border_color};
                border-radius: 16px;
            }}
        """)
        self.refresh_window_style()

        self.window_flash_timer.stop()
        if duration > 0:
            self.window_flash_timer.start(duration)

    def clear_window_flash_state(self):
        if hasattr(self, "main_container"):
            if self.main_container.styleSheet() != self._main_container_base_style:
                self.main_container.setStyleSheet(self._main_container_base_style)
                self.refresh_window_style()

    def update_feedback_hint(self, text="", level="neutral"):
        if not hasattr(self, "lbl_feedback_hint"):
            return

        style_map = {
            "neutral": ("#909399", "#F4F4F5"),
            "success": ("#67C23A", "#F0F9EB"),
            "warning": ("#E6A23C", "#FDF6EC"),
            "error": ("#F56C6C", "#FEF0F0"),
        }
        color, bg = style_map.get(level, style_map["neutral"])
        display_text = text or self._t(
            "feedback.hint.default",
            "监听成功后会自动替换；如果失败，这里会提示你如何一键反馈给 AI。")
        compact = bool(getattr(self, "_compact_mode", (False, False))[0])
        if compact and len(display_text) > 30:
            display_text = display_text[:30] + "…"

        self.lbl_feedback_hint.setText(display_text)
        self.lbl_feedback_hint.setMaximumHeight(40 if compact else 48)
        self.lbl_feedback_hint.setStyleSheet(
            f"color: {color}; font-size: 11px; padding: 5px 8px; "
            f"background: {bg}; border-radius: 9px;")

    def build_feedback_reason_text(self, result):
        result = result or {}
        reason = result.get("reason", "")

        if reason == "invalid_block":
            return self._t(
                "feedback.reason.invalid_block",
                "AI 上一次返回的内容不是完整替换块格式。请严格补齐 `<<<< 文件:`、`<<<< 查找`、`====`、`>>>> 替换`，不要输出解释或完整文件。")

        if reason == "no_tab":
            return self._t(
                "feedback.reason.no_tab",
                "当前没有打开文件，无法自动应用。请在已有文件上下文下重新生成替换块。")

        diagnostics = result.get("diagnostics", [])
        diagnostic_types = {
            item.get("type")
            for item in diagnostics
            if isinstance(item, dict)
        }

        if "open_failed" in diagnostic_types:
            return self._t(
                "feedback.reason.open_failed",
                "AI 指定的目标文件路径不存在或无法打开。请基于当前项目结构重新确认文件路径，并在每个多文件替换块前正确填写 `<<<< 文件:`。")

        if result.get("multi_match_failed") or "multi_match" in diagnostic_types:
            return self._t(
                "feedback.reason.multi_match",
                "查找代码在当前文件里命中了多处。自动监听模式为了避免误改没有应用。请加入更多上下文，确保 `<<<< 查找` 下面的旧代码只命中一处。")

        if result.get("zero_match_failed") or "zero_match" in diagnostic_types:
            return self._t(
                "feedback.reason.zero_match",
                "查找代码没有在当前文件中命中，说明 AI 参考的代码和当前文件不一致。请基于下方当前完整代码重新生成替换块，旧代码必须逐字符一致。")

        if reason == "partial_failed":
            return self._t(
                "feedback.reason.partial_failed",
                "部分替换成功、部分失败。请只针对失败的替换块重新生成更精确的替换块。")

        return self._t(
            "feedback.reason.default",
            "自动替换没有成功。请基于下面提供的当前完整代码，重新生成可直接应用的替换块。")

    def build_feedback_summary_text(self, failure_type, result=None):
        result = result or {}
        if failure_type == "invalid_block":
            return self._t(
                "feedback.summary.invalid_block",
                "这次复制的内容不是完整替换格式，可能缺少 <<<< 查找、==== 或 >>>> 替换。你可以点击「复制反馈给AI」，让 AI 严格按替换块格式重新输出。")
        if failure_type == "unique_match_failed" and result.get("multi_match_failed"):
            return self._t(
                "feedback.summary.multi_match",
                "当前文件里有多处相似代码，自动模式为了避免误改，暂时没有执行。你可以点击「复制反馈给AI」，让 AI 重新生成更精确的替换块。")
        if result.get("zero_match_failed"):
            return self._t(
                "feedback.summary.zero_match",
                "AI 返回的旧代码没有在当前文件中找到，说明它记忆的代码版本不对。点击「复制反馈给AI」，可把当前完整代码重新发给它。")
        if failure_type == "no_tab":
            return self._t(
                "feedback.summary.no_tab",
                "当前没有打开文件，所以这次自动替换没有执行。请先打开文件后再继续。")
        return self._t(
            "feedback.summary.default",
            "自动替换这次没有成功。你可以点击「复制反馈给AI」，把失败原因和当前完整代码一起发给 AI 重新生成。")

    def build_feedback_diagnostics_text(self, result):
        """把替换引擎返回的结构化失败诊断转成给 AI 的可读说明。"""
        result = result or {}
        diagnostics = result.get("diagnostics", [])
        files = result.get("files", [])

        if not diagnostics and files:
            for file_result in files:
                file_path = file_result.get("file", "") if isinstance(file_result, dict) else ""
                for diagnostic in file_result.get("diagnostics", []) if isinstance(file_result, dict) else []:
                    if isinstance(diagnostic, dict):
                        item = dict(diagnostic)
                        item.setdefault("file", file_path)
                        diagnostics.append(item)

        if not diagnostics:
            failed_blocks = result.get("failed_blocks", [])
            if failed_blocks:
                return self._t("feedback.diagnostics.failed_details", "失败详情：") + "\n" + "\n".join(f"- {item}" for item in failed_blocks)
            return self._t("feedback.diagnostics.empty", "暂无更详细诊断。")

        lines = [self._t("feedback.diagnostics.title", "失败诊断：")]
        for index, item in enumerate(diagnostics, 1):
            if not isinstance(item, dict):
                continue

            file_path = item.get("file", "")
            failure_type = item.get("type", "unknown")
            match_count = item.get("match_count", "")
            old_preview = item.get("old_preview", "")
            suggestion = item.get("suggestion", "")

            type_label = {
                "zero_match": self._t("feedback.diagnostics.type.zero_match", "旧代码未命中"),
                "multi_match": self._t("feedback.diagnostics.type.multi_match", "旧代码命中多处"),
                "unique_match_failed": self._t("feedback.diagnostics.type.unique_match_failed", "唯一命中校验失败"),
                "open_failed": self._t("feedback.diagnostics.type.open_failed", "目标文件无法打开"),
                "unknown": self._t("feedback.diagnostics.type.unknown", "未知失败"),
            }.get(failure_type, failure_type)

            lines.append(f"{index}. {self._t('feedback.diagnostics.type', '类型')}：{type_label}")
            if file_path:
                lines.append(f"   {self._t('feedback.diagnostics.file', '文件')}：{file_path}")
            if match_count != "":
                lines.append(f"   {self._t('feedback.diagnostics.match_count', '命中次数')}：{match_count}")
            if old_preview:
                lines.append(f"   {self._t('feedback.diagnostics.old_preview', '旧代码预览')}：{old_preview}")
            if suggestion:
                lines.append(f"   {self._t('feedback.diagnostics.suggestion', '修正建议')}：{suggestion}")

        return "\n".join(lines)

    def cache_failed_feedback(self, failure_type, clipboard_text, result=None):
        result = result or {}
        tab = self.current_tab()
        file_path = tab.file_path if tab and hasattr(tab, 'file_path') else ""
        current_code = tab.text_code.toPlainText() if tab else ""

        for file_result in result.get("files", []):
            if not isinstance(file_result, dict):
                continue
            if file_result.get("fail_count", 0) <= 0:
                continue

            candidate_path = file_result.get("file", "")
            if candidate_path:
                file_path = candidate_path

                if hasattr(self, "tab_widget"):
                    for index in range(self.tab_widget.count()):
                        candidate_tab = self.tab_widget.widget(index)
                        if getattr(candidate_tab, "file_path", "") == candidate_path:
                            current_code = candidate_tab.text_code.toPlainText()
                            break
                break

        self.last_failed_feedback_summary = self.build_feedback_summary_text(failure_type, result)
        self.last_failed_feedback_payload = {
            "failure_type": failure_type,
            "file_path": file_path,
            "clipboard_text": clipboard_text or "",
            "result": result or {},
            "current_code": current_code,
        }
        if hasattr(self, "btn_feedback_ai"):
            self.btn_feedback_ai.setEnabled(bool(current_code.strip()))
        self.update_feedback_hint(self.last_failed_feedback_summary, "warning")

    def clear_failed_feedback(self):
        self.last_failed_feedback_payload = None
        self.last_failed_feedback_summary = ""
        if hasattr(self, "btn_feedback_ai"):
            self.btn_feedback_ai.setEnabled(False)
        self.update_feedback_hint("", "neutral")

    def build_feedback_text_for_ai(self):
        payload = self.last_failed_feedback_payload
        if not payload:
            return ""

        file_path = payload.get("file_path", "")
        file_name = os.path.basename(file_path) if file_path else self._t("feedback.untitled_file", "未命名文件")
        current_code = payload.get("current_code", "")
        clipboard_text = payload.get("clipboard_text", "")
        result = payload.get("result", {})
        failure_type = payload.get("failure_type", "unknown")
        reason_text = self.build_feedback_reason_text(result)
        diagnostics_text = self.build_feedback_diagnostics_text(result)

        failure_map = {
            "invalid_block": self._t("feedback.failure.invalid_block", "替换块格式不完整"),
            "unique_match_failed": self._t("feedback.failure.unique_match_failed", "自动监听命中校验未通过"),
            "partial_failed": self._t("feedback.failure.partial_failed", "部分替换失败"),
            "replace_failed": self._t("feedback.failure.replace_failed", "自动替换失败"),
            "open_failed": self._t("feedback.failure.open_failed", "目标文件无法打开"),
            "no_tab": self._t("feedback.failure.no_tab", "当前没有打开文件"),
            "unknown": self._t("feedback.failure.unknown", "自动替换未成功"),
        }
        failure_label = failure_map.get(failure_type, self._t("feedback.failure.unknown", "自动替换未成功"))

        project_hint = ""
        if hasattr(self, "build_project_structure_context_text"):
            try:
                project_context = self.build_project_structure_context_text()
                if project_context:
                    project_hint = (
                        f"\n{self._t('feedback.project_context.title', '【当前项目结构上下文】')}\n"
                        f"{self._t('feedback.project_context.hint', '下面是当前项目结构，请用它校对 `<<<< 文件:` 路径。如果不需要多文件修改，可以忽略。')}\n\n"
                        f"{project_context}\n"
                    )
            except Exception:
                project_hint = ""

        return self._t(
            "feedback.ai_prompt",
            "请你重新为我生成可直接应用的代码替换块。\n"
            "注意：请只输出替换块，不要解释，不要输出完整文件，不要使用 Markdown 代码围栏包裹。\n\n"
            "我的本地替换工具只能识别以下格式：\n\n"
            "<<<< 文件: path/to/file.py\n"
            "<<<< 查找\n"
            "[原代码，必须与当前文件中的代码完全一致，保留缩进和空行]\n"
            "====\n"
            "[修改后的新代码]\n"
            ">>>> 替换\n\n"
            "硬性规则：\n"
            "- 如果要修改多个文件，每段替换块前都必须加 `<<<< 文件:`；\n"
            "- `<<<< 查找` 下面的旧代码必须与当前文件逐字符一致，包括缩进、空行、标点；\n"
            "- 如果上次失败是“未命中”，请不要复用上次旧代码，请基于【当前完整代码】重写查找块；\n"
            "- 如果上次失败是“命中多处”，请加入更多上下文，确保只命中一处；\n"
            "- 不要输出解释文字，只输出可以直接应用的替换块。\n\n"
            "本次自动替换失败信息如下：\n"
            "- 失败类型：{failure_label}\n"
            "- 关联文件：{file_name}\n"
            "- 完整路径：{file_path}\n"
            "- 原因说明：{reason_text}\n\n"
            "{diagnostics_text}\n"
            "{project_hint}\n"
            "【你上一次返回的替换内容】\n"
            "请参考它的意图，但不要盲目复用旧代码。\n\n"
            "{clipboard_text}\n\n"
            "【当前完整代码】\n"
            "请以这里的代码为唯一依据重新生成替换块。\n\n"
            "{current_code}\n",
            failure_label=failure_label,
            file_name=file_name,
            file_path=file_path or self._t("feedback.path_missing", "未获取到"),
            reason_text=reason_text,
            diagnostics_text=diagnostics_text,
            project_hint=project_hint,
            clipboard_text=clipboard_text,
            current_code=current_code,
        )

    def copy_failed_feedback_for_ai(self):
        feedback_text = self.build_feedback_text_for_ai()
        if not feedback_text.strip():
            QMessageBox.information(
                self,
                self._t("feedback.copy.empty.title", "提示"),
                self._t("feedback.copy.empty.message", "当前没有可反馈给 AI 的失败内容。请先触发一次自动监听失败。"))
            return

        QApplication.clipboard().setText(feedback_text)
        self.update_feedback_hint(
            self._t("feedback.copy.success.hint", "反馈内容已复制。现在直接回到 AI 聊天窗口粘贴发送即可。"),
            "success")
        QMessageBox.information(
            self,
            self._t("feedback.copy.success.title", "已复制反馈内容"),
            self._t(
                "feedback.copy.success.message",
                "✅ 已将失败原因、原始替换内容和当前完整代码复制到剪贴板。\n\n直接粘贴发给 AI，让它重新生成替换块即可。")
        )
