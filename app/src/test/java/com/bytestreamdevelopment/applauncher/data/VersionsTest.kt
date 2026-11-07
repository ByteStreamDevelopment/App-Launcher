package com.bytestreamdevelopment.applauncher.data

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
    @Test fun normalize() = assertEquals("1.0", Versions.normalize(" V1.0 "))
}
