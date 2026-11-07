package com.shopguard.ai.ui.theme

import androidx.compose.ui.graphics.Color

// ─── Light Theme Primary Palette ───────────────────────────────────────────
val BgPage        = Color(0xFFF5F7FB)   // Page / scaffold background
val BgCard        = Color(0xFFFFFFFF)   // Cards and surfaces
val BgSubtle      = Color(0xFFEAF2FF)   // Elevated / subtle tinted bg
val BgMuted       = Color(0xFFF1F5F9)   // Muted input / secondary bg

val BorderLight   = Color(0xFFE2E8F0)   // Default border
val BorderMedium  = Color(0xFFCBD5E1)   // Stronger divider

val PrimaryBlue      = Color(0xFF2563EB)   // Brand blue — buttons, links
val PrimaryBlueLight = Color(0xFFEAF2FF)   // Blue tint bg
val PrimaryBlueDark  = Color(0xFF1D4ED8)   // Hover / pressed blue

val TextDark  = Color(0xFF172033)   // Headings & primary text
val TextMid   = Color(0xFF64748B)   // Secondary descriptive text
val TextMuted = Color(0xFF94A3B8)   // Labels, disclaimers, placeholders

// ─── Status / Semantic Colors ───────────────────────────────────────────────
val StatusGreen      = Color(0xFF16A34A)
val StatusGreenLight = Color(0xFFDCFCE7)
val StatusAmber      = Color(0xFFD97706)
val StatusAmberLight = Color(0xFFFEF3C7)
val StatusRed        = Color(0xFFDC2626)
val StatusRedLight   = Color(0xFFFEE2E2)
val StatusOrange     = Color(0xFFEA580C)
val StatusOrangeLight= Color(0xFFFEF0E6)
val StatusSlate      = Color(0xFF64748B)
val StatusSlateLight = Color(0xFFF1F5F9)

// ─── Demo Mode ──────────────────────────────────────────────────────────────
val DemoPurple          = Color(0xFF7C3AED)
val DemoPurpleLight     = Color(0xFFA78BFA)
val DemoBadgeBackground = Color(0xFFF5F3FF)

// ─── Utility ────────────────────────────────────────────────────────────────
val GreenSuccess = StatusGreen

// ─── Backward-Compatible Aliases (keep old names pointing to new values) ───
// Background tokens
val NavyDarkest    = BgPage
val NavyBackground = BgPage
val NavySurface    = BgCard
val NavyElevated   = BgSubtle
val NavyBorder     = BorderLight
val NavyBorderLight= BorderMedium

// Accent tokens
val CyanAccent     = PrimaryBlue
val CyanAccentGlow = PrimaryBlueLight
val ElectricBlue   = PrimaryBlue

// Security state tokens
val ArmedGreen     = StatusGreen
val ArmedGreenGlow = StatusGreenLight
val DisarmedAmber  = StatusAmber
val DisarmedAmberGlow = StatusAmberLight
val AlertRed       = StatusRed
val AlertRedGlow   = StatusRedLight
val PartialOrange  = StatusOrange
val OfflineGray    = StatusSlate

// Text tokens (critical: TextWhite → TextDark for light bg)
val TextWhite   = TextDark    // Was white on dark; now dark on light
val TextPrimary = TextDark
val TextSecondary= TextMid
