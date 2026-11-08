package com.bytestreamdevelopment.bytedroide.install

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow

sealed interface InstallEvent {
    val fullName: String

    data class WaitingForUser(override val fullName: String) : InstallEvent
    data class Success(override val fullName: String) : InstallEvent
    data class Aborted(override val fullName: String) : InstallEvent
    data class Failure(override val fullName: String, val message: String) : InstallEvent
}

/** Leitet Ergebnisse vom [InstallResultReceiver] an die Oberfläche weiter. */
object InstallEvents {
    private val _events = MutableSharedFlow<InstallEvent>(extraBufferCapacity = 32)
    val events: SharedFlow<InstallEvent> = _events

    fun emit(event: InstallEvent) {
        _events.tryEmit(event)
    }
}
