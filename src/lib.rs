// SPDX-License-Identifier: MIT OR Apache-2.0
//! SigmaOS-file-writer — Minimal distraction-free text writer.
//!
//! Provides text buffer modeling, word/character metric calculation,
//! auto-save state serialization, and focus-mode typography preferences.
//!
//! Inspired by Omarchy's serene, text-focused desktop environment, Hyprland's
//! smooth UI transitions, and Catppuccin Mocha's eye-friendly reading contrast.
//!
//! Principles: deterministic text metrics, zero `unsafe`, pure `std`.

#![forbid(unsafe_code)]

use std::fmt;

// ── Error types ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WriterError {
    CursorOutOfBounds { line: usize, col: usize },
    InvalidFontSize(u32),
    InvalidLineHeight(u32),
    EmptyBuffer,
    InvalidEncoding(String),
}

impl fmt::Display for WriterError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::CursorOutOfBounds { line, col } => write!(f, "cursor position ({line}, {col}) out of document bounds"),
            Self::InvalidFontSize(sz) => write!(f, "font size {sz}pt out of valid range (8..=72)"),
            Self::InvalidLineHeight(h) => write!(f, "line height {h}% out of valid range (100..=300)"),
            Self::EmptyBuffer => write!(f, "document buffer is empty"),
            Self::InvalidEncoding(e) => write!(f, "invalid character encoding: {e}"),
        }
    }
}

impl std::error::Error for WriterError {}

// ── Typography & Focus Preferences ───────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ThemeMode {
    MochaDark,
    LatteLight,
    Monochrome,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WriterConfig {
    pub font_family: String,
    pub font_size_pt: u32,
    pub line_height_pct: u32,
    pub theme: ThemeMode,
    pub spellcheck: bool,
    pub autosave_interval_sec: u32,
}

impl Default for WriterConfig {
    fn default() -> Self {
        Self {
            font_family: "JetBrains Mono".into(),
            font_size_pt: 14,
            line_height_pct: 160,
            theme: ThemeMode::MochaDark,
            spellcheck: true,
            autosave_interval_sec: 30,
        }
    }
}

impl WriterConfig {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn set_font_size(&mut self, size: u32) -> Result<(), WriterError> {
        if !(8..=72).contains(&size) {
            return Err(WriterError::InvalidFontSize(size));
        }
        self.font_size_pt = size;
        Ok(())
    }

    pub fn set_line_height(&mut self, pct: u32) -> Result<(), WriterError> {
        if !(100..=300).contains(&pct) {
            return Err(WriterError::InvalidLineHeight(pct));
        }
        self.line_height_pct = pct;
        Ok(())
    }
}

// ── Document Metrics & Buffer ────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct TextStats {
    pub words: usize,
    pub characters: usize,
    pub lines: usize,
    pub reading_time_minutes: usize,
}

#[derive(Debug, Clone, Default)]
pub struct DocumentBuffer {
    content: String,
    cursor_line: usize,
    cursor_col: usize,
    dirty: bool,
}

impl DocumentBuffer {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn set_text(&mut self, text: impl Into<String>) {
        self.content = text.into();
        self.cursor_line = 0;
        self.cursor_col = 0;
        self.dirty = true;
    }

    pub fn text(&self) -> &str {
        &self.content
    }

    pub fn is_dirty(&self) -> bool {
        self.dirty
    }

    pub fn mark_saved(&mut self) {
        self.dirty = false;
    }

    pub fn append(&mut self, slice: &str) {
        self.content.push_str(slice);
        self.dirty = true;
    }

    pub fn stats(&self) -> TextStats {
        let chars = self.content.chars().count();
        let words = self.content.split_whitespace().count();
        let lines = if self.content.is_empty() { 0 } else { self.content.lines().count() };
        let reading_time_minutes = (words + 199) / 200; // ~200 wpm reading speed
        TextStats {
            words,
            characters: chars,
            lines,
            reading_time_minutes,
        }
    }

    pub fn move_cursor(&mut self, line: usize, col: usize) -> Result<(), WriterError> {
        let lines: Vec<&str> = self.content.lines().collect();
        if lines.is_empty() {
            if line == 0 && col == 0 {
                self.cursor_line = 0;
                self.cursor_col = 0;
                return Ok(());
            }
            return Err(WriterError::CursorOutOfBounds { line, col });
        }
        if line >= lines.len() {
            return Err(WriterError::CursorOutOfBounds { line, col });
        }
        if col > lines[line].chars().count() {
            return Err(WriterError::CursorOutOfBounds { line, col });
        }
        self.cursor_line = line;
        self.cursor_col = col;
        Ok(())
    }
}

// ── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn config_validation_bounds() {
        // Arrange
        let mut cfg = WriterConfig::default();
        // Act
        let valid_font = cfg.set_font_size(16);
        let bad_font = cfg.set_font_size(120);
        let valid_height = cfg.set_line_height(180);
        let bad_height = cfg.set_line_height(50);

        // Assert
        assert!(valid_font.is_ok());
        assert_eq!(bad_font, Err(WriterError::InvalidFontSize(120)));
        assert!(valid_height.is_ok());
        assert_eq!(bad_height, Err(WriterError::InvalidLineHeight(50)));
    }

    #[test]
    fn text_stats_calculation() {
        // Arrange
        let mut buf = DocumentBuffer::new();
        buf.set_text("SigmaOS is an operating system inspired by Omarchy.\nClean, calm, and distraction-free.");

        // Act
        let stats = buf.stats();

        // Assert
        assert_eq!(stats.lines, 2);
        assert_eq!(stats.words, 12);
        assert!(stats.characters > 50);
        assert_eq!(stats.reading_time_minutes, 1);
    }

    #[test]
    fn cursor_movement_and_bounds() {
        // Arrange
        let mut buf = DocumentBuffer::new();
        buf.set_text("First line\nSecond line");

        // Act
        let valid = buf.move_cursor(1, 5);
        let bad_line = buf.move_cursor(5, 0);
        let bad_col = buf.move_cursor(0, 50);

        // Assert
        assert!(valid.is_ok());
        assert_eq!(bad_line, Err(WriterError::CursorOutOfBounds { line: 5, col: 0 }));
        assert_eq!(bad_col, Err(WriterError::CursorOutOfBounds { line: 0, col: 50 }));
    }

    #[test]
    fn buffer_dirty_and_save_lifecycle() {
        // Arrange
        let mut buf = DocumentBuffer::new();
        assert!(!buf.is_dirty());

        // Act
        buf.append("typing a quick note...");
        assert!(buf.is_dirty());

        buf.mark_saved();
        assert!(!buf.is_dirty());
    }

    #[test]
    fn empty_buffer_stats() {
        // Arrange
        let buf = DocumentBuffer::new();
        // Act
        let s = buf.stats();
        // Assert
        assert_eq!(s.words, 0);
        assert_eq!(s.lines, 0);
        assert_eq!(s.characters, 0);
    }

    #[test]
    fn error_display_formatting() {
        // Arrange
        let err = WriterError::InvalidFontSize(5);
        // Act & Assert
        assert_eq!(format!("{err}"), "font size 5pt out of valid range (8..=72)");
    }
}
