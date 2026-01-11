package com.tradez.order.common.strategy.py38;

import com.tradez.order.service.IAccountService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import javax.annotation.PostConstruct;
import javax.annotation.Resource;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

@Slf4j
@Component
public class StrategyManager {

    @Resource
    IAccountService accountService;

    // 注入策略服务（核心业务逻辑）
    @Resource
    HighFrequencyMarketMakingStrategyV38Service strategyService;

    @Resource
    VariationalHedgingStrategyV38Service hedgingStrategyService;


    // 注入 RedisTemplate (虽然策略服务内部已注入，但这里用于初始化配置映射)
    @Resource
    StringRedisTemplate stringRedisTemplate;

    // 调度器，用于定期执行策略主循环
    private ScheduledExecutorService scheduler;

    // 待执行的合约 ID 列表  动态获取合约列表
    private final List<String> gridContractIdList = Arrays.asList("10000003", "10000004", "10000005", "10000006");
    private final List<String> hedgeContractIdList = Arrays.asList("10000001", "10000002");
    // 静态配置 Map (只用于传递配置对象，不包含状态)
    private Map<String, SymbolGridManager> configManagerMap;

    /**
     * 服务启动时（或首次访问时）初始化静态配置 Map。
     */
    @PostConstruct
    public void initConfigMap() {
        this.configManagerMap = new HashMap<>();
        GridStrategyConfig strategyConfig = new GridStrategyConfig();

        for (String contractId : gridContractIdList) {
            // 创建一个临时的 SymbolGridManager 实例，用于传递静态配置。
            SymbolGridManager configHolderMgr = new SymbolGridManager(
                    stringRedisTemplate,
                    contractId,
                    "CONFIG_HOLDER", // 伪账户ID
                    strategyConfig
            );
            configManagerMap.put(contractId, configHolderMgr);
        }
        log.info("策略配置 Map 初始化完成，交易对: {}", gridContractIdList);
    }

    /**
     * 【通过 Controller 调用启动】
     */
    public synchronized String start() {
        if (scheduler != null && !scheduler.isShutdown()) {
            return "策略已在运行中。";
        }

        // 重新初始化调度器
        scheduler = Executors.newSingleThreadScheduledExecutor();

        long initialDelay = 1; // 首次延迟 1 秒
        long delay = 50;       // 每次任务执行完毕后，等待 3 秒再启动下一次任务
        // 确保了任务之间至少有 3 秒的间隔，避免重叠。
        scheduler.scheduleWithFixedDelay(() -> {
            try {
                // *** 核心变化：每次循环动态查询账户列表 ***
                List<String> thirdAccountIdList = accountService.getWgActiveAccountIds();

                if (thirdAccountIdList == null || thirdAccountIdList.isEmpty()) {
                    log.error("未查询到任何活跃账户ID，本次循环跳过。");
                    return;
                }

                log.info("--- 策略执行循环开始：{} 个账户, {} 个交易对 ---",
                        thirdAccountIdList.size(), gridContractIdList.size());

                // 核心调用：将动态加载的账户列表传入主服务
                strategyService.executeStrategy(thirdAccountIdList, gridContractIdList, configManagerMap);

                hedgingStrategyService.executeStrategy(thirdAccountIdList, hedgeContractIdList);


                log.info("--- 策略执行循环结束 ---");

            } catch (Exception e) {
                log.error("策略执行异常", e);
            }
        }, initialDelay, delay, TimeUnit.SECONDS);
        log.info("策略 HighFrequencyMarketMakingStrategyV38 已通过API启动，交易对: {}，开始动态加载账户...", gridContractIdList);
        return "策略启动成功。";
    }

    /**
     * 【通过 Controller 调用停止】
     */
    public synchronized String stop() {
        if (scheduler != null && !scheduler.isShutdown()) {
            scheduler.shutdownNow();
            log.info("策略 HighFrequencyMarketMakingStrategyV38 已通过API停止。");
            return "策略已成功停止。";
        }
        return "策略未在运行中或已停止。";
    }
}
