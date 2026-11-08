package com.bytestreamdevelopment.bytedroide.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class VersionsTest {
    @Test fun gleicheVersionMitPrefix() = assertFalse(Versions.isNewer("v2.5.0", "2.5.0"))
    @Test fun neuerePatchVersion() = assertTrue(Versions.isNewer("v2.5.1", "2.5.0"))
    @Test fun numerischNichtLexikalisch() = assertTrue(Versions.isNewer("v2.10.0", "2.9.3"))
    @Test fun installierteIstNeuer() = assertFalse(Versions.isNewer("v2.4.0", "2.5.0"))
    @Test fun fehlendeStellenAlsNull() = assertFalse(Versions.isNewer("v2.5", "2.5.0"))
    @Test fun nichtNumerischeTagsUnterschiedlich() = assertTrue(Versions.isNewer("nightly-2", "nightly-1"))
    @Test fun fertigeVersionNeuerAlsBeta() = assertTrue(Versions.isNewer("1.1.0", "1.1.0-beta"))
    @Test fun betaAelterAlsFertige() = assertFalse(Versions.isNewer("1.1.0-beta", "1.1.0"))
    @Test fun betaNummernNatuerlich() = assertTrue(Versions.isNewer("1.1.0-beta10", "1.1.0-beta9"))
    @Test fun neueBetaNachAlterVersion() = assertTrue(Versions.isNewer("v1.2.0-beta1", "1.1.0"))
    @Test fun rcNachBeta() = assertTrue(Versions.isNewer("2.0.0-rc1", "2.0.0-beta3"))
    @Test fun normalize() = assertEquals("1.0", Versions.normalize(" V1.0 "))
}
