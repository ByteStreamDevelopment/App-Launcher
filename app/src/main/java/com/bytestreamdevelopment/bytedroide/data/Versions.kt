package com.bytestreamdevelopment.bytedroide.data

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
            // Gleiche Zahlen: Vorabversion ("-beta") ist älter als die fertige Version (wie bei SemVer)
            val sa = suffix(a)
            val sb = suffix(b)
            return when {
                sa.isEmpty() -> sb.isNotEmpty()
                sb.isEmpty() -> false
                else -> compareNatural(sa, sb) > 0
            }
        }
        // Nicht vergleichbar (z. B. "nightly") -> jede Abweichung gilt als Update.
        return true
    }

    /** Teil nach den Versionsnummern, z. B. "beta2" bei "1.2.0-beta2". */
    private fun suffix(v: String): String {
        val m = Regex("^[0-9]+(?:[._][0-9]+)*").find(v) ?: return v
        return v.substring(m.range.last + 1).trimStart('-', '+', '.', '_').lowercase()
    }

    /** Vergleicht Text mit Zahlen darin natürlich ("beta10" > "beta9"). */
    private fun compareNatural(a: String, b: String): Int {
        val ta = Regex("[0-9]+|[^0-9]+").findAll(a).map { it.value }.toList()
        val tb = Regex("[0-9]+|[^0-9]+").findAll(b).map { it.value }.toList()
        for (i in 0 until minOf(ta.size, tb.size)) {
            val x = ta[i]
            val y = tb[i]
            val c = if (x[0].isDigit() && y[0].isDigit()) {
                x.toBigInteger().compareTo(y.toBigInteger())
            } else {
                x.compareTo(y)
            }
            if (c != 0) return c
        }
        return ta.size - tb.size
    }

    private fun numericParts(v: String): List<Int>? {
        val parts = v.split('.', '-', '+', '_')
            .takeWhile { it.isNotEmpty() && it.all(Char::isDigit) }
            .map { it.toIntOrNull() ?: return null }
        return parts.ifEmpty { null }
    }
}
