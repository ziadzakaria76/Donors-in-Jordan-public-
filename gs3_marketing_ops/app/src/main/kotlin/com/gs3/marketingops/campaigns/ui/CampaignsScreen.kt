package com.gs3.marketingops.campaigns.ui

import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import com.gs3.marketingops.R
import com.gs3.marketingops.ui.components.Gs3EmptyState
import com.gs3.marketingops.ui.components.Gs3ScreenScaffold

@Composable
internal fun CampaignsScreen(modifier: Modifier = Modifier) {
    Gs3ScreenScaffold(
        title = stringResource(R.string.nav_campaigns),
        modifier = modifier,
    ) { innerPadding ->
        Gs3EmptyState(
            title = stringResource(R.string.empty_campaigns_title),
            body = stringResource(R.string.empty_campaigns_body),
            modifier = Modifier.padding(innerPadding),
        )
    }
}
