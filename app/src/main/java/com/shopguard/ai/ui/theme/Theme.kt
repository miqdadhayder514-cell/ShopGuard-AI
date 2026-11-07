package com.shopguard.ai.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightSecurityColorScheme = lightColorScheme(
    primary            = PrimaryBlue,
    onPrimary          = Color.White,
    primaryContainer   = PrimaryBlueLight,
    onPrimaryContainer = PrimaryBlueDark,
    secondary          = StatusGreen,
    onSecondary        = Color.White,
    secondaryContainer = StatusGreenLight,
    onSecondaryContainer = StatusGreen,
    tertiary           = StatusAmber,
    onTertiary         = Color.White,
    background         = BgPage,
    onBackground       = TextDark,
    surface            = BgCard,
    onSurface          = TextDark,
    surfaceVariant     = BgSubtle,
    onSurfaceVariant   = TextMid,
    outline            = BorderLight,
    outlineVariant     = BorderMedium,
    error              = StatusRed,
    onError            = Color.White
)

@Composable
fun ShopGuardTheme(
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = LightSecurityColorScheme,
        typography  = Typography,
        content     = content
    )
}
