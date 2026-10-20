package com.equifolio.optimizer;

import java.nio.file.*;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.test.util.ReflectionTestUtils;
import static org.junit.jupiter.api.Assertions.*;

class NativeRegimeLifecycleTest {
    @TempDir Path directory;

    @Test void managedWorkerReceivesDatabaseAndDailySettingsAndStopsWithBackend() throws Exception {
        Path project=directory.resolve("project"), ml=project.resolve("ml");Files.createDirectories(ml);
        Path marker=project.resolve("ready.txt"), script=ml.resolve("worker.py");
        Files.writeString(script,"import os,time\nfrom pathlib import Path\nPath('ready.txt').write_text(os.environ['DB_NAME']+'|'+os.environ['REGIME_DAILY_ENABLED'])\ntime.sleep(30)\n");
        var lifecycle=new NativeRegimeLifecycle();
        ReflectionTestUtils.setField(lifecycle,"managed",true);
        ReflectionTestUtils.setField(lifecycle,"model","native");
        ReflectionTestUtils.setField(lifecycle,"python","python3");
        ReflectionTestUtils.setField(lifecycle,"script",script.toString());
        ReflectionTestUtils.setField(lifecycle,"url","http://127.0.0.1:19579");
        ReflectionTestUtils.setField(lifecycle,"token","");
        ReflectionTestUtils.setField(lifecycle,"jdbcUrl","jdbc:postgresql://127.0.0.1:5432/equifolio_test");
        ReflectionTestUtils.setField(lifecycle,"username","postgres");
        ReflectionTestUtils.setField(lifecycle,"password","test-only");
        try {
            lifecycle.start();
            assertTimeoutPreemptively(Duration.ofSeconds(10),()->{while(!Files.exists(marker))Thread.sleep(50);});
            assertEquals("equifolio_test|true",Files.readString(marker));
            Process child=(Process)ReflectionTestUtils.getField(lifecycle,"child");
            lifecycle.start();
            assertSame(child,ReflectionTestUtils.getField(lifecycle,"child"));
            lifecycle.stop();
            assertTrue(child.waitFor(5,java.util.concurrent.TimeUnit.SECONDS));
        } finally { lifecycle.stop(); }
    }

    @Test void externalWorkerIsNotLaunchedLocallyWhenManagementIsDisabled() {
        var lifecycle=new NativeRegimeLifecycle();
        ReflectionTestUtils.setField(lifecycle,"managed",false);
        lifecycle.start();
        assertNull(ReflectionTestUtils.getField(lifecycle,"child"));
    }
}
