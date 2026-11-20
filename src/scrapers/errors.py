class CrawlCompletenessError(RuntimeError):
    """So URL crawl duoc khong khop tong job website cong bo."""


class SalarySessionError(RuntimeError):
    """Website khong cong nhan storage_state nen salary van bi khoa."""


class JobFilteredOutError(RuntimeError):
    """Job detail hop le nhung khong thuoc pham vi IT cua project."""
