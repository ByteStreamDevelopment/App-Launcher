package com.bytestreamdevelopment.applauncher.data

/** Vergleicht Release-Tags (z. B. "v2.5.0") mit versionName der installierten App ("2.5.0"). */
object Versions {
    fun normalize(version: String): String = version.trim().removePrefix("v").removePrefix("V")

    /** true, wenn [latest] neuer ist als [installed]. */
    fun isNewer(latest: String, installed: String): Boolean {
        val a = normalize(latest)
        val b = normalize(installed)
        if (a.equals(b, ignoreCase = true)) return false
        val pa = numericParts(a)
        val pb = numericParts(b)
        if (pa != null && pb != null) {
            for (i in 0 until maxOf(pa.size, pb.size)) {
                val x = pa.getOrElse(i) { 0 }
                val y = pb.getOrElse(i) { 0 }
                if (x != y) return x > y
            }
            return false
        }
        // Nicht vergleichbar (z. B. "nightly") -> jede Abweichung gilt als Update.
        return true
    }

    private fun numericParts(v: String): List<Int>? {
        val parts = v.split('.', '-', '+', '_')
            .takeWhile { it.isNotEmpty() && it.all(Char::isDigit) }
            .map { it.toIntOrNull() ?: return null }
        return parts.ifEmpty { null }
    }
}
